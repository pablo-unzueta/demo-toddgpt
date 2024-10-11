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
from src.toddgpt.parsers.parse_hhtda import get_uv_vis_data as get_uv_vis_data_hhtda
from src.toddgpt.parsers.parse_wpbe import get_uv_vis_data as get_uv_vis_data_wpbe
import numpy as np
import matplotlib.pyplot as plt
import base64
import requests
import json

logging.basicConfig(level=logging.INFO)


class OptimizeMoleculeInput(BaseModel):
    atoms_dict: AtomsDict


class OptimizeMolecule(BaseTool):
    name: str = "optimize_molecule_for_spectrum"
    description: str = "This is the first tool you should use to optimize the geometry of a molecule to generate a UV-Vis spectrum."
    args_schema: Type[BaseModel] = OptimizeMoleculeInput

    def _run(self, atoms_dict: AtomsDict):
        output_opt_dir = Path("./public/scratch/minimize")
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
        output_hessian_dir = Path("./public/scratch/initcond")
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

        output_wigner_dir = Path("./public/scratch/wigner")
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
        "Use this tool to run a TD-DFT calculation, only after using run_hessian. "
        "Requires two separate inputs: 'atoms_dict' (an AtomsDict object) and 'method' (a string)."
    )
    args_schema: Type[BaseModel] = RunTDDFTInput

    def _run(self, atoms_dict: AtomsDict, method: str):
        output_wigner_dir = Path("./public/scratch/wigner")
        output_td_dir = Path(f"./public/scratch/{method}")
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
    method: str


class GenerateSpectrum(BaseTool):
    name: str = "generate_spectrum"
    description: str = "Use this tool to generate a UV-Vis spectrum after using optimize_molecule_for_spectrum, run_hessian, and run_td_dft."
    args_schema: Type[BaseModel] = SpectraInput

    def _run(self, method: str):
        logging.info(f"Generating spectrum for {method}")
        logging.info(f"Reading files from ./public/scratch/{method}")
        logging.info(f"Writing output to ./public/scratch/spectra/{method}.png")
        self.plot_spectra(method)
        return (
            f"Generated spectra can be viewed at ./public/scratch/spectra/{method}.png"
        )

    def plot_spectra(self, method: str):
        logging.info(f"Plotting spectrum for {method}")
        spectra_dir = Path("./public/scratch/spectra")
        spectra_dir.mkdir(parents=True, exist_ok=True)
        uv_vis_data = []
        for file in Path(f"./public/scratch/{method}").glob("*.out"):
            if method == "hhtda":
                data = get_uv_vis_data_hhtda(file)
            elif method == "wpbe":
                data = get_uv_vis_data_wpbe(file)
            uv_vis_data.extend(data)

        uv_vis_data = np.array(
            uv_vis_data
        )  # first column is wavelengths, second is osc strength
        energy_data = uv_vis_data[:, 0]
        osc_strength_data = uv_vis_data[:, 1]
        osc_strength_data /= osc_strength_data.max()

        grid = np.linspace(100, 350, 551)
        self.spectrum(energy_data, osc_strength_data, grid, plot_label=method)

    def gaussian(self, x, x0, sigma):
        return np.exp(-((x - x0) ** 2) / (2 * sigma**2)) / (sigma * np.sqrt(2 * np.pi))

    def spectrum(self, energy, osc_strength, grid, plot_label):
        output = np.zeros(len(grid))
        for i, en in enumerate(energy):
            gauss = self.gaussian(
                grid, 1239.841 / en, 30
            )  # Use wavelength instead of energy
            output += gauss * osc_strength[i]

        plt.plot(grid, output, linewidth=3, label=plot_label)
        plt.xlabel("Wavelength (nm)")
        plt.ylabel("Intensity (a.u.)")
        plt.yticks([])
        plt.title(f"UV-Vis Spectrum - {plot_label}")
        plt.legend()
        plt.savefig(f"./public/scratch/spectra/{plot_label}.png")
        plt.close()


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


class WavelengthResponse(BaseModel):
    wavelength: float


class CheckGeneratedSpectraInput(BaseModel):
    path: str


class CheckGeneratedSpectra(BaseTool):
    name: str = "check_generated_spectra"
    description: str = "Use this tool to analyze an UV-Vis spectrum and find the wavelength of the maximum absorbance."
    args_schema: Type[BaseModel] = CheckGeneratedSpectraInput

    def _run(self, path: str):
        # Load the image from the path or URL
        if isinstance(path, str):
            base64_image = encode_image(path)  # Encode the image to base64

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            }

            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "What is the wavelength of the maximum absorbance?",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                "max_tokens": 4096,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "steps": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "output": {"type": "number"},
                                        },
                                        "required": ["output"],
                                        "additionalProperties": False,
                                    },
                                },
                                "final_answer": {"type": "string"},
                            },
                            "required": ["steps", "final_answer"],
                            "additionalProperties": False,
                        },
                        "strict": True,
                    },
                },
            }

            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            return response.json()
            # content = json.loads(response.json()["choices"][0]["message"]["content"])
            # return content
            # return f"Generated Spectra has a lambda max at {content['steps'][0]['output']} nm"
