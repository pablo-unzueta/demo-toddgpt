import numpy as np
import re
import os
import argparse
from typing import Union, List

# Utility libraries
from . import atom_data
from . import units
from . import manage_xyz
from pathlib import Path

# => Read TeraChem Hessian (Yak Shave) <= #


def read_tc_hessian(
    filename,
    symbols=None,
):
    """Reads information from TeraChem Hessian binary file

    Params:
        filename (string) - name for TeraChem Hessian file
        symbols (list of string) - list of atomic symbols to override in case
            TeraChem gets the atomic numbers wrong (e.g., if ECPs are used)

    Returns:
        geom ((natoms,4) np.ndarray) - molecule geometry
        hess ((natoms*3,natoms*3) np.ndarray) - molecule Hessian

    """

    fh = open(filename, "rb")
    # Next int is number of atoms
    natom = np.frombuffer(fh.read(4), dtype=np.int32)[0]
    # Next int is number of points in stencil
    npoint = np.frombuffer(fh.read(4), dtype=np.int32)
    # Next double is displacement in au
    displacement = np.frombuffer(fh.read(8), dtype=np.float64)
    # Next natom*4 doubles are (x,y,z,Z) for atoms in au
    G = np.frombuffer(fh.read(natom * 4 * 8), dtype=np.float64)
    G = np.reshape(G, (natom, 4))
    # Geometry structure
    geom = []
    for A in range(natom):
        geom.append(
            (
                atom_data.atom_symbol_table[int(G[A, 3])]
                if not symbols
                else symbols[A],
                G[A, 0],
                G[A, 1],
                G[A, 2],
            )
        )

    # Next (3*natom)**2 doubles are hessian
    hess = np.frombuffer(fh.read(9 * natom * natom * 8), dtype=np.float64)
    hess = np.reshape(hess, (natom * 3, natom * 3))

    # TODO: Dipole derivatives/polarizabilities

    return geom, hess


# => COM/Inertial Frame Transforms <= #


def eckart_frame(
    geom,
    masses,
):
    """Moves the molecule to the Eckart frame

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
    COM = np.sum(manage_xyz.xyz_to_np(geom) * np.outer(masses, [1.0] * 3), 0) / np.sum(
        masses
    )
    # Inertial tensor
    I = np.zeros((3, 3))
    for atom, mass in zip(geom, masses):
        I[0, 0] += mass * (atom[1] - COM[0]) * (atom[1] - COM[0])
        I[0, 1] += mass * (atom[1] - COM[0]) * (atom[2] - COM[1])
        I[0, 2] += mass * (atom[1] - COM[0]) * (atom[3] - COM[2])
        I[1, 0] += mass * (atom[2] - COM[1]) * (atom[1] - COM[0])
        I[1, 1] += mass * (atom[2] - COM[1]) * (atom[2] - COM[1])
        I[1, 2] += mass * (atom[2] - COM[1]) * (atom[3] - COM[2])
        I[2, 0] += mass * (atom[3] - COM[2]) * (atom[1] - COM[0])
        I[2, 1] += mass * (atom[3] - COM[2]) * (atom[2] - COM[1])
        I[2, 2] += mass * (atom[3] - COM[2]) * (atom[3] - COM[2])
    I /= np.sum(masses)
    # Principal moments/Principle axes of inertial tensor
    L, O = np.linalg.eigh(I)

    # Eckart geometry
    geom2 = manage_xyz.np_to_xyz(
        geom,
        np.dot(
            (manage_xyz.xyz_to_np(geom) - np.outer(np.ones((len(masses),)), COM)), O
        ),
    )

    return COM, L, O, geom2


def vibrational_basis(
    geom,
    masses,
):
    """Compute the vibrational basis in mass-weighted Cartesian coordinates.
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
    TR = np.zeros((3 * len(geom), 6))
    # Translations
    TR[0::3, 0] = np.sqrt(masses)  # +X
    TR[1::3, 1] = np.sqrt(masses)  # +Y
    TR[2::3, 2] = np.sqrt(masses)  # +Z
    # Rotations in the Eckart frame
    for A, mass in enumerate(masses):
        mass_12 = np.sqrt(mass)
        for j in range(3):
            TR[3 * A + j, 3] = +mass_12 * (
                G[A, 1] * O[j, 2] - G[A, 2] * O[j, 1]
            )  # + Gy Oz - Gz Oy
            TR[3 * A + j, 4] = -mass_12 * (
                G[A, 0] * O[j, 2] - G[A, 2] * O[j, 0]
            )  # - Gx Oz + Gz Ox
            TR[3 * A + j, 5] = +mass_12 * (
                G[A, 0] * O[j, 1] - G[A, 1] * O[j, 0]
            )  # + Gx Oy - Gy Ox

    # Single Value Decomposition (review)
    U, s, V = np.linalg.svd(TR, full_matrices=True)

    # The null-space of TR
    B = U[:, 6:]

    return B


# => Normal Mode Computation <= #


def normal_modes(
    geom,  # Optimized geometry in au
    hess,  # Hessian matrix in au
    masses,  # Masses in au
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
    m = np.ravel(np.outer(masses, [1.0] * 3))

    # mass-weight hessian
    hess2 = hess / np.sqrt(np.outer(m, m))

    # Find normal modes (project translation/rotations before)
    B = vibrational_basis(geom, masses)
    h, U3 = np.linalg.eigh(np.dot(B.T, np.dot(hess2, B)))
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
    print("=> Normal Mode Analysis <=\n")

    print("T = %.1f K" % ((1.0 / beta) / units.units["au_per_K"]))
    print("")

    print(
        "%-4s: %18s %18s %18s"
        % (
            "Mode",
            "Frequency(cm-1)",
            "ZPVE(au)",
            "Vib.Energy(au)",
        )
    )
    for I, wval in enumerate(w):
        fval = np.tanh(beta * wval / 2.0)
        print(
            "%-4d: %18.10f %18.10f %18.10f"
            % (
                I + 1,
                wval / units.units["au_per_cminv"],
                0.5 * wval,
                0.5 * (1.0 / fval - 1.0) * wval,
            )
        )
    print("")

    # TODO: Intensity, vibrational temperature, vibrational entropy
    # TODO: Translational/Rotational properties?

    f = np.tanh(beta * w / 2.0)
    print("ZPVE = %18.10f au" % (np.sum(0.5 * w)))
    print("FTVE = %18.10f au" % (np.sum(0.5 / f * w)))
    print("")

    print("=> End Normal Mode Analysis <=\n")


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

    Q2 = np.reshape(Q[:, index], (len(geom), 3))
    thetas = np.linspace(0.0, 2.0 * np.pi, ntheta, endpoint=False)
    geoms = []
    for theta in thetas:
        dxyz = dx * Q2 * np.sin(theta)
        xyz2 = manage_xyz.xyz_to_np(geom) + dxyz
        geoms.append(manage_xyz.np_to_xyz(geom, xyz2))
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
        output (list) - captured output messages

    Result:
        x is written to xfilename in Angstrom if xfilename is not None
        p is written to pfilename in au if pfilename is not None
        x, p are written to fms90filename in fms90 units if fms90filename is not None
        v is written to vfilename in amber units if vfilename is not None

    """

    output = []
    x0 = manage_xyz.xyz_to_np(geom)
    p0 = np.zeros_like(x0)
    dx = np.zeros_like(x0)
    dp = np.zeros_like(x0)

    # Sample each normal mode
    KEnormal = 0.0
    PEnormal = 0.0
    for i in range(len(w)):
        wval = w[i]
        Qval = Q[:, i]
        ft = np.tanh(wval * beta / 2.0)
        sigmax = np.sqrt(1.0 / (2.0 * ft * wval))
        sigmap = np.sqrt(wval / (2.0 * ft))
        xstar = np.random.normal(loc=0.0, scale=sigmax)
        pstar = np.random.normal(loc=0.0, scale=sigmap)
        dx += np.reshape(Qval * xstar, dx.shape)
        dp += np.reshape(Qval * pstar, dp.shape)
        KEnormal += 0.5 * pstar**2
        PEnormal += 0.5 * wval**2 * xstar**2

    dp *= np.outer(masses, [1.0] * 3)

    ZPVE = 0.5 * np.sum(w)
    ZPKEquantum = 0.5 * ZPVE
    ZPPEquantum = 0.5 * ZPVE
    FTVE = 0.5 * np.sum(1.0 / np.tanh(w * beta / 2.0) * w)
    FTKEquantum = 0.5 * FTVE
    FTPEquantum = 0.5 * FTVE
    KEcartesian = 0.5 * np.sum(dp**2 / np.outer(masses, [1.0, 1.0, 1.0]))
    PEcartesian = 0.5 * np.einsum("i,ij,j->", np.ravel(dx), hess, np.ravel(dx))

    output.append("Wigner Sample:")
    output.append("%10s: %24s %24s" % ("Energy", "KE", "PE"))
    output.append("%10s: %24.16E %24.16E" % ("ZPVE", ZPKEquantum, ZPPEquantum))
    output.append("%10s: %24.16E %24.16E" % ("FTVE", FTKEquantum, FTPEquantum))
    output.append("%10s: %24.16E %24.16E" % ("Normal", KEnormal, PEnormal))
    output.append("%10s: %24.16E %24.16E" % ("Cartesian", KEcartesian, PEcartesian))
    output.append("")

    # Removing Net Translational Velocity
    if remove_vcom:
        dv = dp / np.outer(masses, [1.0] * 3)
        dv -= sum(dp) / sum(masses)
        dp = dv * np.outer(masses, [1.0] * 3)

    x = x0 + dx
    p = p0 + dp
    v = p / np.outer(masses, [1.0] * 3)

    # Write XYZ files and fms90 .dat files
    geomx = manage_xyz.np_to_xyz(geom, x)
    geomp = manage_xyz.np_to_xyz(geom, p)
    geomv = manage_xyz.np_to_xyz(geom, v)
    if xfilename:
        manage_xyz.write_xyz(xfilename, geomx)  # In Angstrom (xyz default) for position
    if pfilename:
        manage_xyz.write_xyz(pfilename, geomp, scale=1.0)  # In au for momentum
    if vfilename:
        manage_xyz.write_xyz(
            vfilename,
            geomv,  # In AMBER
            scale=units.units["ang_per_au"] * units.units["au_per_fs"] * 1.0e3 / 20.455,
        )
    if fms90filename:
        manage_xyz.write_fms90(fms90filename, geomx, geomp)

    return x, p, KEnormal, PEnormal, output


def run_wigner(
    hessian_file: Union[Path, str] = "Hessian.bin",
    temp: float = 0.0,
    wigner: bool = True,
    wigner_dir: Path = Path("./wigner"),
    wigner_N: int = 5,
    atomic_symbols: List[str] = None,
    alternate_masses: List[str] = None,
):
    # Default parameters
    hessian_file = hessian_file
    temp = temp
    wigner = wigner
    wigner_dir = wigner_dir
    wigner_N = wigner_N
    atomic_symbols = atomic_symbols
    alternate_masses = alternate_masses
    # Read Hessian
    geom, hess = read_tc_hessian(hessian_file, atomic_symbols)
    masses = [atom_data.mass_table[atom[0].upper()] for atom in geom]

    beta = float("Inf") if temp == 0.0 else 1.0 / (temp * units.units["au_per_K"])

    w, Q = normal_modes(geom, hess, masses)

    normal_mode_analysis(w, Q, beta)

    atomic_symbols = None if not atomic_symbols else eval(atomic_symbols)
    geom, hess = read_tc_hessian(hessian_file, atomic_symbols)
    masses = [atom_data.mass_table[atom[0].upper()] for atom in geom]

    # replace default masses for atom types if requested
    if alternate_masses:
        import copy

        masses_dict = copy.copy(atom_data.mass_table)
        for atom_mass in alternate_masses:
            mobj = re.match("(\S+)-(\d+\.\d+)", atom_mass)
            atom = mobj.group(1).upper()
            mass = float(mobj.group(2)) * units.units["au_per_amu"]
            masses_dict[atom] = mass
        masses = [masses_dict[atom[0].upper()] for atom in geom]

    beta = float("Inf") if temp == 0.0 else 1.0 / (temp * units.units["au_per_K"])

    w, Q = normal_modes(geom, hess, masses)

    normal_mode_analysis(w, Q, beta)

    if wigner:
        output = []
        output.append("=> Wigner Sampling <=\n")
        output.append(f"Saving Wigner sample files in: {wigner_dir}")
        output.append(f"Number of Wigner samples: {wigner_N}")
        output.append("")
        if not os.path.exists(wigner_dir):
            os.makedirs(wigner_dir)
        KE = 0.0
        PE = 0.0
        for N in range(wigner_N):
            x, p, KE2, PE2, sample_output = wigner_sample(
                geom,
                hess,
                masses,
                w,
                Q,
                remove_vcom=True,
                xfilename=f"{wigner_dir}/x{N:04d}.xyz",
                pfilename=f"{wigner_dir}/p{N:04d}.xyz",
                vfilename=f"{wigner_dir}/v{N:04d}.xyz",
                fms90filename=f"{wigner_dir}/Geometry{N:04d}.dat",
                beta=beta,
            )
            KE += KE2
            PE += PE2
            output.extend(sample_output)
        KE /= wigner_N
        PE /= wigner_N

        output.append(f"Average Wigner KE: {KE:24.16E}")
        output.append(f"Average Wigner PE: {PE:24.16E}")
        output.append("")
        output.append("=> End Wigner Sampling <=\n")

        # Save output to file
        with open(f"{wigner_dir}/0000_wigner_sampling_output.txt", "w") as f:
            f.write("\n".join(output))
