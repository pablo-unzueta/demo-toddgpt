import numpy as np
import re
import os
import argparse
# Utility libraries
import atom_data
import units
import manage_xyz

# => Read TeraChem Hessian (Yak Shave) <= #

def read_tc_hessian(
    filename,
    symbols=None,
    ):

    """ Reads information from TeraChem Hessian binary file

    Params:
        filename (string) - name for TeraChem Hessian file
        symbols (list of string) - list of atomic symbols to override in case
            TeraChem gets the atomic numbers wrong (e.g., if ECPs are used)

    Returns:
        geom ((natoms,4) np.ndarray) - molecule geometry
        hess ((natoms*3,natoms*3) np.ndarray) - molecule Hessian

    """

    fh = open(filename, 'rb')
    # Next int is number of atoms
    natom = np.frombuffer(fh.read(4), dtype=np.int32)[0]
    # Next int is number of points in stencil
    npoint = np.frombuffer(fh.read(4), dtype=np.int32)
    # Next double is displacement in au
    displacement = np.frombuffer(fh.read(8), dtype=np.float64)
    # Next natom*4 doubles are (x,y,z,Z) for atoms in au
    G = np.frombuffer(fh.read(natom*4*8), dtype=np.float64)
    G = np.reshape(G,(natom,4))
    # Geometry structure
    geom = []
    for A in range(natom):
        geom.append((
            atom_data.atom_symbol_table[int(G[A,3])] if not symbols else symbols[A],
            G[A,0],
            G[A,1],
            G[A,2],
            ))

    # Next (3*natom)**2 doubles are hessian
    hess = np.frombuffer(fh.read(9*natom*natom*8), dtype=np.float64)
    hess = np.reshape(hess, (natom*3,natom*3))

    # TODO: Dipole derivatives/polarizabilities

    return geom, hess

# => COM/Inertial Frame Transforms <= #

def eckart_frame(
    geom,
    masses,
    ):

    """ Moves the molecule to the Eckart frame

    Params:
        geom ((natoms,4) np.ndarray) - Contains atom symbol and xyz coordinates
        masses ((natoms) np.ndarray) - Atom masses

    Returns:
        COM ((3), np.ndarray) - Molecule center of mess
        L ((3), np.ndarray) - Principal moments
        O ((3,3), np.ndarray)- Principle axes of inertial tensor
        geom2 ((natoms,4 np.ndarray) - Contains new geometry (atom symbol and xyz coordinates)

    """

    # Center of mass
    COM = np.sum(manage_xyz.xyz_to_np(geom) * np.outer(masses, [1.0]*3), 0) / np.sum(masses)
    # Inertial tensor
    I = np.zeros((3,3))
    for atom, mass in zip(geom, masses):
        I[0,0] += mass * (atom[1] - COM[0]) * (atom[1] - COM[0])
        I[0,1] += mass * (atom[1] - COM[0]) * (atom[2] - COM[1])
        I[0,2] += mass * (atom[1] - COM[0]) * (atom[3] - COM[2])
        I[1,0] += mass * (atom[2] - COM[1]) * (atom[1] - COM[0])
        I[1,1] += mass * (atom[2] - COM[1]) * (atom[2] - COM[1])
        I[1,2] += mass * (atom[2] - COM[1]) * (atom[3] - COM[2])
        I[2,0] += mass * (atom[3] - COM[2]) * (atom[1] - COM[0])
        I[2,1] += mass * (atom[3] - COM[2]) * (atom[2] - COM[1])
        I[2,2] += mass * (atom[3] - COM[2]) * (atom[3] - COM[2])
    I /= np.sum(masses)
    # Principal moments/Principle axes of inertial tensor
    L, O = np.linalg.eigh(I)

    # Eckart geometry
    geom2 = manage_xyz.np_to_xyz(geom, np.dot((manage_xyz.xyz_to_np(geom) - np.outer(np.ones((len(masses),)), COM)), O))

    return COM, L, O, geom2

def vibrational_basis(
    geom,
    masses,
    ):

    """ Compute the vibrational basis in mass-weighted Cartesian coordinates.
    This is the null-space of the translations and rotations in the Eckart frame.

    Params:
        geom (geometry struct) - minimimum geometry structure
        masses (list of float) - masses for the geometry

    Returns:
        B ((3*natom, 3*natom-6) np.ndarray) - orthonormal basis for vibrations. Mass-weighted cartesians in rows, mass-weighted vibrations in columns.

    """

    # Compute Eckart frame geometry
    COM, L, O, geom2 = eckart_frame(geom, masses)
    G = manage_xyz.xyz_to_np(geom2)

    # Known basis functions for translations
    TR = np.zeros((3*len(geom),6))
    # Translations
    TR[0::3,0] = np.sqrt(masses) # +X
    TR[1::3,1] = np.sqrt(masses) # +Y
    TR[2::3,2] = np.sqrt(masses) # +Z
    # Rotations in the Eckart frame
    for A, mass in enumerate(masses):
        mass_12 = np.sqrt(mass)
        for j in range(3):
            TR[3*A+j,3] = + mass_12 * (G[A,1] * O[j,2] - G[A,2] * O[j,1]) # + Gy Oz - Gz Oy
            TR[3*A+j,4] = - mass_12 * (G[A,0] * O[j,2] - G[A,2] * O[j,0]) # - Gx Oz + Gz Ox
            TR[3*A+j,5] = + mass_12 * (G[A,0] * O[j,1] - G[A,1] * O[j,0]) # + Gx Oy - Gy Ox

    # Single Value Decomposition (review)
    U, s, V = np.linalg.svd(TR, full_matrices=True)

    # The null-space of TR
    B = U[:,6:]

    return B

# => Normal Mode Computation <= #

def normal_modes(
    geom,       # Optimized geometry in au
    hess,       # Hessian matrix in au
    masses,     # Masses in au
    ):

    """
    Params:
        geom ((natoms,4) np.ndarray) - atoms symbols and xyz coordinates
        hess ((natoms*3,natoms*3) np.ndarray) - molecule hessian
        masses ((natoms) np.ndarray) - masses

    Returns:
        w ((natoms*3 - 6) np.ndarray)  - normal frequencies
        Q ((natoms*3, natoms*3 - 6) np.ndarray)  - normal modes

    """

    # masses repeated 3x for each atom (unravels)
    m = np.ravel(np.outer(masses,[1.0]*3))

    # mass-weight hessian
    hess2 = hess / np.sqrt(np.outer(m,m))

    # Find normal modes (project translation/rotations before)
    B = vibrational_basis(geom, masses)
    h, U3 = np.linalg.eigh(np.dot(B.T,np.dot(hess2,B)))
    U = np.dot(B, U3)

    # TEST: Find normal modes (without projection translations/rotations)
    # RMP: Matches TC output for PYP - same differences before/after projection
    # h2, U2 = np.linalg.eigh(hess2)
    # h2 = h2[6:]
    # U2 = U2[:,6:]
    # for hval, hval2 in zip(h,h2):
    #     wval = np.sqrt(hval) / units['au_per_cminv']
    #     wval2 = np.sqrt(hval2) / units['au_per_cminv']
    #     print '%10.6E %10.6E %11.3E' % (wval, wval2, np.abs(wval - wval2))

    # Normal frequencies
    w = np.sqrt(h)
    # Imaginary frequencies
    w[h < 0.0] = -np.sqrt(-h[h < 0.0])

    # Normal modes
    Q = U / np.outer(np.sqrt(m), np.ones((U.shape[1],)))

    return w, Q

# => Normal Mode Analysis <= #

def normal_mode_analysis(
    w,
    Q,
    beta,
    ):

    print('=> Normal Mode Analysis <=\n')

    print('T = %.1f K' % ((1.0 / beta) / units.units['au_per_K']))
    print('')

    print('%-4s: %18s %18s %18s' % (
        'Mode',
        'Frequency(cm-1)',
        'ZPVE(au)',
        'Vib.Energy(au)',
        ))
    for I, wval in enumerate(w):
        fval = np.tanh(beta * wval / 2.0)
        print('%-4d: %18.10f %18.10f %18.10f' % (
            I+1,
            wval/units.units['au_per_cminv'],
            0.5 * wval,
            0.5 * (1.0 / fval - 1.0) * wval,
            ))
    print('')

    # TODO: Intensity, vibrational temperature, vibrational entropy
    # TODO: Translational/Rotational properties?

    f = np.tanh(beta * w / 2.0)
    print('ZPVE = %18.10f au' % (np.sum(0.5 * w)))
    print('FTVE = %18.10f au' % (np.sum(0.5  / f * w)))
    print('')

    print('=> End Normal Mode Analysis <=\n')


# => Normal Mode Visualization <= #

def viz_normal_mode(
    filename,
    geom,
    Q,
    index=0,
    ntheta=20,
    dx=1.0,
    ):

    """
    Params:
        filename (string) - output filename of Wigner sample
        geom ((natoms,4) np.ndarray) - minimium geometry
        Q ((natoms*3, natoms*3 - 6) np.ndarray) - normal mode coordinates
        index=0 (int) - index of normal mode coordinates to visualize
        ntheta=20 (int) - number of frames to visualize
        dx=1.0 (float) - amplitude of normal mode vibration

    Returns:

    """

    Q2 = np.reshape(Q[:,index],(len(geom),3))
    thetas = np.linspace(0.0,2.0*np.pi,ntheta,endpoint=False)
    geoms=[]
    for theta in thetas:
        dxyz = dx * Q2 * np.sin(theta)
        xyz2 = manage_xyz.xyz_to_np(geom) + dxyz
        geoms.append(manage_xyz.np_to_xyz(geom,xyz2))
    manage_xyz.write_xyzs(filename, geoms)

# => Wigner Sampling Utility <= #

def wigner_sample(
    geom,
    hess,
    masses,
    w,
    Q,
    remove_vcom=False,
    xfilename=None,
    pfilename=None,
    vfilename=None,
    fms90filename=None,
    beta=0.0,
    ):

    """
    Params:
        geom ((natoms,4) np.ndarray) - optimized geometry (atom symbols and xyz coordinates)
        hess ((natoms*3,natoms*3)) - molecule hessian
        masses ((natoms) np.ndarray) - atom masses
        w ((natoms*3 - 6) np.ndarray) - harmonic frequencies
        Q ((natoms*3,natoms*3 - 6) np.ndarray) - normal mode coordinates in au
        remove_vcom - Remove net velocity?
        xfilename (string) - filename for Wigner sample in x -> XYZ in Angstrom
        pfilename (string) - filename for Wigner sample in p -> XYZ in au
        vfilename (string) - filename for Wigner sample velocity in amber units
        fms90filename (string) - filename for Wigner sample in fms90 units
        beta (float) - 1.0 / (kB * T) in au

    Returns:
        x ((natoms,3) np.ndarray) - Wigner sample in au
        p ((natoms,3) np.ndarray) - Wigner sample in au

    Result:
        x is written to xfilename in Angstrom if xfilename is not None
        p is written to pfilename in au if pfilename is not None
        x, p are written to fms90filename in fms90 units if fms90filename is not None
        v is written to vfilename in amber units if vfilename is not None

    """

    x0 = manage_xyz.xyz_to_np(geom)
    p0 = np.zeros_like(x0)
    dx = np.zeros_like(x0)
    dp = np.zeros_like(x0)

    # Sample each normal mode
    KEnormal = 0.0
    PEnormal = 0.0
    for i in range(len(w)):
        wval = w[i]
        Qval = Q[:,i]
        # if wval < 0.0:
        #     raise RuntimeError('Negative frequency: %.6f. Cannot sample Wigner.' % wval)
        ft = np.tanh(wval * beta / 2.0)
        sigmax = np.sqrt(1.0 / (2.0 * ft * wval))
        sigmap = np.sqrt(wval / (2.0 * ft))
        xstar = np.random.normal(loc=0.0,scale=sigmax)
        pstar = np.random.normal(loc=0.0,scale=sigmap)
        dx += np.reshape(Qval * xstar, dx.shape)
        dp += np.reshape(Qval * pstar, dp.shape)
        KEnormal += 0.5 * pstar**2
        PEnormal += 0.5 * wval**2 * xstar**2

    dp *= np.outer(masses,[1.0]*3)

    ZPVE = 0.5 * np.sum(w)
    ZPKEquantum = 0.5 * ZPVE
    ZPPEquantum = 0.5 * ZPVE
    FTVE = 0.5 * np.sum(1.0 / np.tanh(w * beta / 2.0) * w)
    FTKEquantum = 0.5 * FTVE
    FTPEquantum = 0.5 * FTVE
    KEcartesian = 0.5 * np.sum(dp**2 / np.outer(masses,[1.0,1.0,1.0]))
    PEcartesian = 0.5 * np.einsum('i,ij,j->', np.ravel(dx), hess, np.ravel(dx))

    print('Wigner Sample:')
    print('%10s: %24s %24s' % ('Energy', 'KE', 'PE'))
    print('%10s: %24.16E %24.16E' % ('ZPVE', ZPKEquantum, ZPPEquantum))
    print('%10s: %24.16E %24.16E' % ('FTVE', FTKEquantum, FTPEquantum))
    print('%10s: %24.16E %24.16E' % ('Normal', KEnormal, PEnormal))
    print('%10s: %24.16E %24.16E' % ('Cartesian', KEcartesian, PEcartesian))
    print('')

    # Removing Net Translational Velocity
    if remove_vcom:
        dv = dp / np.outer(masses, [1.0]*3)
        dv -= sum(dp) / sum(masses)
        dp = dv * np.outer(masses, [1.0]*3)

    x = x0 + dx
    p = p0 + dp
    v = p / np.outer(masses, [1.0]*3)

    # Write XYZ files and fms90 .dat files
    geomx = manage_xyz.np_to_xyz(geom, x)
    geomp = manage_xyz.np_to_xyz(geom, p)
    geomv = manage_xyz.np_to_xyz(geom, v)
    if xfilename:
        manage_xyz.write_xyz(xfilename, geomx)            # In Angstrom (xyz default) for position
    if pfilename:
        manage_xyz.write_xyz(pfilename, geomp, scale=1.0) # In au for momentum
    if vfilename:
        manage_xyz.write_xyz(vfilename, geomv,            # In AMBER
            scale = units.units['ang_per_au'] * units.units['au_per_fs'] * 1.E3 / 20.455,
            )
    if fms90filename:
        manage_xyz.write_fms90(fms90filename,geomx,geomp)

    return x, p, KEnormal, PEnormal


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--hessian', help='TeraChem Hessian.bin file', type=str, required=True)
    parser.add_argument('--temp', help='Temperature in K', type=float, default=0.0)
    parser.add_argument('--viz', dest='viz', help='Visualize normal modes', action='store_true')
    parser.add_argument('--no-viz', dest='viz', help='Do not visualize normal modes', action='store_false')
    parser.set_defaults(viz=False)
    parser.add_argument('--viz-dir', help='Directory for normal mode visualization files', type=str, default='viz')
    parser.add_argument('--viz-dx', help='Displacement of normal mode visualization', type=float, default=40.0)
    parser.add_argument('--wigner', dest='wigner', help='Perform Wigner sampling', action='store_true')
    parser.add_argument('--no-wigner', dest='wigner', help='Do not perform Wigner sampling', action='store_false')
    parser.set_defaults(wigner=False)
    parser.add_argument('--wigner-dir', help='Directory for Wigner samples', type=str, default='wigner')
    parser.add_argument('--wigner-N', help='Number of Wigner samples', type=int, default=1)
    parser.add_argument('--atomic-symbols', help='Optional list of atomic symbols', type=str, default=None)
    parser.add_argument('--alternate-masses', help='Optional list of alternate atomic masses', type=str, default=None, nargs='+')
    # TODO: Option to load masses from some sort of file
    args = parser.parse_args()

    atomic_symbols = None if not args.atomic_symbols else eval(args.atomic_symbols)
    geom, hess = read_tc_hessian(args.hessian, atomic_symbols)
    masses = [atom_data.mass_table[atom[0].upper()] for atom in geom]

    # replace default masses for atom types if requested
    if args.alternate_masses:
        import copy
        masses_dict = copy.copy(atom_data.mass_table)
        for atom_mass in args.alternate_masses:
            mobj = re.match('(\S+)-(\d+\.\d+)', atom_mass)
            atom = mobj.group(1).upper()
            mass = float(mobj.group(2)) * units.units['au_per_amu']
            masses_dict[atom] = mass
        masses = [masses_dict[atom[0].upper()] for atom in geom]

    beta = float('Inf') if args.temp ==0.0 else 1.0 / (args.temp * units.units['au_per_K'])

    w, Q = normal_modes(geom, hess, masses)

    normal_mode_analysis(w, Q, beta)

    if args.viz:
        print('=> Normal Mode Visualization <=\n')
        print('Saving normal mode visualization XYZ files in: %s' % args.viz_dir)
        print('Visualization displacement: %.1f' % args.viz_dx)
        print('')
        if not os.path.exists(args.viz_dir):
            os.makedirs(args.viz_dir)
        for index in range(3*len(geom)-6):
            viz_normal_mode('%s/%04d.xyz' % (args.viz_dir, index), geom, Q, index=index, dx=args.viz_dx)
        print('=> End Normal Mode Visualization <=\n')

    if args.wigner:
        print('=> Wigner Sampling <=\n')
        print('Saving Wigner sample files in: %s' % args.wigner_dir)
        print('Number of Wigner samples: %d' % args.wigner_N)
        print('')
        if not os.path.exists(args.wigner_dir):
            os.makedirs(args.wigner_dir)
        KE = 0.0
        PE = 0.0
        for N in range(args.wigner_N):
            x, p, KE2, PE2 = wigner_sample(
                geom,
                hess,
                masses,
                w,
                Q,
                remove_vcom=True,
                xfilename='%s/x%04d.xyz' % (args.wigner_dir, N),
                pfilename='%s/p%04d.xyz' % (args.wigner_dir, N),
                vfilename='%s/v%04d.xyz' % (args.wigner_dir, N),
                fms90filename='%s/Geometry%04d.dat' % (args.wigner_dir, N),
                beta=beta,
                )
            KE += KE2
            PE += PE2
        KE /= args.wigner_N
        PE /= args.wigner_N

        print('Average Wigner KE: %24.16E' % KE)
        print('Average Wigner PE: %24.16E' % PE)
        print('')

        print('=> End Wigner Sampling <=\n')
