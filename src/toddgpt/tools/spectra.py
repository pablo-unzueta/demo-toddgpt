from typing import List, Type
from pydantic import BaseModel
from langchain_core.tools import BaseTool
from .datatypes import AtomsDict
from .chemcloud_tool import RunTerachem, FindJobExample
from pathlib import Path
from ase.io import read
import os
from .wigner.wigner import run_wigner
import logging
from src.toddgpt.parsers.parse_hhtda import get_uv_vis_data

logging.basicConfig(level=logging.INFO)


class OptimizeMoleculeInput(BaseModel):
    atoms_dict: AtomsDict


class OptimizeMolecule(BaseTool):
    name: str = "optimize_molecule_for_spectrum"
    description: str = "This is the first tool you should use to optimize the geometry of a molecule to generate a UV-Visspectrum."
    args_schema: Type[BaseModel] = OptimizeMoleculeInput

    def _run(self, atoms_dict: AtomsDict):
        output_opt_dir = Path("./scratch/minimize")
        output_opt_dir.mkdir(parents=True, exist_ok=True)
        logging.info("Directory for optimization created at %s", output_opt_dir)

        tc_input = FindJobExample()._run("minimize")
        logging.info("Running TeraChem with minimize job")

        prog_output = RunTerachem()._run(tc_input, atoms_dict)
        with open(output_opt_dir / "tc.out", "w") as f:
            f.write(prog_output.stdout)
        logging.info(f"TeraChem output written to {output_opt_dir}/tc.out")

        prog_output.results.save_files(output_opt_dir)
        logging.info(f"Results saved to {output_opt_dir}")

        return self.grab_optimized_geom(output_opt_dir)

    def grab_optimized_geom(self, output_opt_dir: Path):
        atoms = read(output_opt_dir / "scr.geom/optim.xyz", index=-1, format="extxyz")
        return atoms.get_positions()


class RunHessianInput(BaseModel):
    atoms_dict: AtomsDict


class RunHessian(BaseTool):
    name: str = "run_hessian"
    description: str = "Use this tool to run a Hessian calculation, only after running optimize_molecule_for_spectrum."
    args_schema: Type[BaseModel] = RunHessianInput

    def _run(self, atoms_dict: AtomsDict):
        output_hessian_dir = Path("./scratch/initcond")
        output_hessian_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Directory for Hessian created at {output_hessian_dir}")

        tc_input = FindJobExample()._run("initcond")
        logging.info("Running TeraChem with initcond job")

        prog_output = RunTerachem()._run(tc_input, atoms_dict)
        with open(output_hessian_dir / "tc.out", "w") as f:
            f.write(prog_output.stdout)
        logging.info(f"TeraChem output written to {output_hessian_dir}/tc.out")

        prog_output.results.save_files(output_hessian_dir)
        logging.info(f"Results saved to {output_hessian_dir}")

        output_wigner_dir = Path("./scratch/wigner")
        output_wigner_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Directory for Wigner created at {output_wigner_dir}")
        logging.info("Running Wigner")
        run_wigner(
            hessian_file=output_hessian_dir / "scr.geom/Hessian.bin",
            wigner_dir=output_wigner_dir,
        )


class RunTDDFTInput(BaseModel):
    atoms_dict: AtomsDict
    method: str


class RunTDDFT(BaseTool):
    name: str = "run_td_dft"
    description: str = (
        "Use this tool to run a TD-DFT calculation, only after using run_hessian."
    )
    args_schema: Type[BaseModel] = RunTDDFTInput

    def _run(self, atoms_dict: AtomsDict, method: str):
        output_wigner_dir = Path("./scratch/wigner")
        output_td_dir = Path(f"./scratch/{method}")
        output_td_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Directory for TDDFT created at {output_td_dir}")

        tc_input = FindJobExample()._run(method)
        logging.info(f"Running TeraChem with {method} job")

        for file in output_wigner_dir.glob("x*.xyz"):
            atoms = read(file)
            logging.info(f"Running TeraChem with {method} job")
            prog_output = RunTerachem()._run(
                tc_input,
                AtomsDict(
                    numbers=atoms.get_atomic_numbers(), positions=atoms.get_positions()
                ),
            )
            with open(output_td_dir / file.name.replace(".xyz", ".out"), "w") as f:
                f.write(prog_output.stdout)
            logging.info(
                f"TeraChem output written to {output_td_dir}/{file.name.replace('.xyz', '.out')}"
            )


class SpectraInput(BaseModel):
    td_dft_dir: Path
    method: str


class GenerateSpectrum(BaseTool):
    name: str = "generate_spectrum"
    description: str = "Use this tool to generate a UV-Vis spectrum after using optimize_molecule_for_spectrum, run_hessian, and run_td_dft."
    args_schema: Type[BaseModel] = SpectraInput

    def _run(self, td_dft_dir: Path, method: str):
        logging.info(f"Generating spectrum for {method}")
        logging.info(f"Reading files from {td_dft_dir}")
        logging.info(f"Writing output to ./scratch/spectra/{method}")
        spectra_dir = Path(f"./scratch/spectra/{method}")
        spectra_dir.mkdir(parents=True, exist_ok=True)
        self.plot_spectra(td_dft_dir)

    def plot_spectra(self, td_dft_dir: Path):
        logging.info(f"Plotting spectrum for {td_dft_dir}")
        uv_vis_data = []
        for file in td_dft_dir.glob("*.out"):
            data = get_uv_vis_data(file)
            uv_vis_data.append([data])
        print(uv_vis_data)
        logging.info(f"UV-Vis data: {uv_vis_data}")
