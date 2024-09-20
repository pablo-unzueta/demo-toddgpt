import os
from pathlib import Path
import numpy as np

# print(f"Python path: {sys.path}")
from ase import units

# from langchain.agents import tool
# Import things that are needed generically
from pydantic import BaseModel, PrivateAttr
from langchain.tools import BaseTool
from qcio import CalcType, FileInput, ProgramInput, ProgramOutput, Structure

from src.toddgpt.tools.datatypes import AtomsDict

try:
    from chemcloud import CCClient

    print("Successfully imported CCClient")
except ImportError as e:
    print(f"Import error: {e}")

from typing import Optional, Type


class JobDescription(BaseModel):
    job_name: str
    job_description: str


class FindJobExample(BaseTool):
    name: str = "find_job_example"
    description: str = (
        "Use this tool to find a similar tc_input file to pass to RunTerachem tool."
    )
    args_schema: Type[BaseModel] = JobDescription

    def _run(self, job_name: str) -> str:
        return self.find_job_example(job_name)

    def find_job_example(self, job_name: str) -> Optional[str]:
        example_dir = Path("src/toddgpt/tools/example_inputs")
        for dir in example_dir.iterdir():
            if dir.is_dir() and dir.stem == job_name:
                example_file = dir / "tc_input"
                if example_file.exists():
                    with open(example_file, "r") as f:
                        return f.read()
        raise ValueError(f"No example input found for job {job_name}")


class TerachemInput(BaseModel):
    tc_input: str
    atoms_dict: AtomsDict


class RunTerachem(BaseTool):
    name: str = "run_terachem"
    description: str = (
        "Use this tool to run a terachem calculation using the ChemCloud API."
    )
    args_schema: Type[BaseModel] = TerachemInput

    _chemcloud_client: Optional[CCClient] = PrivateAttr(default=None)

    def __init__(self):
        super().__init__()

    def _run(
        self,
        tc_input: str,
        atoms_dict: AtomsDict,
    ) -> ProgramOutput:
        return self.run_terachem(tc_input, atoms_dict)

    def setup_file_qcio(self, tc_input: str, atoms_dict: AtomsDict) -> FileInput:
        """
        Useful for creating a FileInput object for run_terachem.
        """
        structure = Structure(
            symbols=atoms_dict.symbols,
            geometry=np.array(atoms_dict.positions) / units.Bohr,
        )
        xyz_str = structure.to_xyz()
        file_inp = FileInput(
            files={"tc.in": tc_input, "geom.xyz": xyz_str}, cmdline_args=["tc.in"]
        )
        return file_inp

    def run_terachem(
        self,
        tc_input: str,
        atoms_dict: AtomsDict,
    ) -> ProgramOutput:
        """
        Useful for running a TeraChem calculation.
        """
        if self._chemcloud_client is None:
            self._chemcloud_client = self.initialize_chemcloud_client()

        if tc_input:
            # Use FileInput if tc_input is provided
            input_obj = self.setup_file_qcio(tc_input, atoms_dict)
        else:
            raise ValueError("Non file based input not supported at this time.")

        future_result = self._chemcloud_client.compute(
            "terachem",
            input_obj,
            collect_files=True,
            queue="pablo",
        )
        prog_output: ProgramOutput = future_result.get()
        return prog_output

    def initialize_chemcloud_client(self) -> CCClient:
        """
        Useful for initializing the ChemCloud client.
        """
        if self._chemcloud_client is None:
            self._chemcloud_client = CCClient()

            if "CHEMCLOUD_USER" not in os.environ:
                raise ValueError("CHEMCLOUD_USER environment variable not set.")

        return self._chemcloud_client
