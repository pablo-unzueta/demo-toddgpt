import os

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


class TerachemInput(BaseModel):
    tc_input: str
    calc_type: CalcType
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
        tc_input: Optional[str],
        calc_type: Optional[CalcType],
        atoms_dict: AtomsDict,
    ) -> str:
        return self.run_terachem(tc_input, calc_type, atoms_dict)

    def setup_qcio(self, atoms_dict: AtomsDict, calc_type: CalcType) -> ProgramInput:
        """
        Useful for creating a ProgramInput object for running energy, gradient, and hessian calculations.
        """
        structure = Structure(
            symbols=atoms_dict.symbols,
            geometry=np.array(atoms_dict.positions) / units.Bohr,
        )
        prog_input = ProgramInput(
            structure=structure,
            calctype=calc_type,
            keywords={"purify": "no", "precision": "double"},
            model={
                "method": "hf",
                "basis": "sto-3g",
            },  # TODO: change to something more realistic
        )
        if calc_type == CalcType.hessian:
            prog_input.keywords["min_tolerance"] = 1e10
        return prog_input

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
            files={"tc.in": tc_input, "coords.xyz": xyz_str}, cmdline_args=["tc.in"]
        )
        return file_inp

    def run_terachem(
        self,
        tc_input: Optional[str],
        calc_type: Optional[CalcType],
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
            # Use ProgramInput if tc_input is not provided
            input_obj = self.setup_qcio(
                atoms_dict, calc_type
            )  # Default to energy calculation

        future_result = self._chemcloud_client.compute(
            "terachem", input_obj, collect_files=True
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
