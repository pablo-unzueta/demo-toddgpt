import os
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Dict

import numpy as np
import requests
from ase.atoms import Atoms
from ase.io import read
from langchain.agents import tool
from langchain_core.tools import BaseTool
from pydantic import BaseModel
from typing import Type

from .datatypes import AtomsDict


@tool
def read_geometry_from_file(file_path: str) -> AtomsDict:
    """Use this tool to read the geometry from a specified file path if provided.

    Args:
        path (Path): Path to the file containing the geometry.

    Returns:
        AtomsDict: AtomsDict object representing the read geometry.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the file format is not supported or the file is invalid.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"The file {file_path} does not exist.")

        atoms = read(path)
        return AtomsDict(
            numbers=atoms.get_atomic_numbers().tolist(),
            positions=atoms.positions.tolist(),
        )
    except Exception as e:
        raise ValueError(f"Error reading geometry from {path}: {str(e)}")


class ExtractMoleculeInput(BaseModel):
    compound_name: str


class ExtractMoleculeFromPubchem(BaseTool):
    name: str = "pubchem_lookup"
    description: str = "Use this tool if the user asks about a specific molecule, but does not provide a file path. Extract molecule information from PubChem based on the compound name using PUG REST API."
    args_schema: Type[BaseModel] = ExtractMoleculeInput

    def _run(self, compound_name: str) -> AtomsDict:
        return self.extract_molecule_from_pubchem(compound_name)

    def extract_molecule_from_pubchem(self, compound_name: str) -> AtomsDict:
        """
            Use this tool if the user asks about a specific molecule, but does not provide a file path.
            Extract molecule information from PubChem based on the compound name using PUG REST API.

        Args:
            compound_name (str): The name of the compound to search for.

        Returns:
            Dict[str, Any]: A dictionary containing the following information:
                - 'atoms': List of atomic numbers
                - 'positions': List of 3D coordinates for each atom
        """

        try:
            # Search for the compound using PUG REST API
            search_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{compound_name}/JSON"
            response = requests.get(search_url)
            response.raise_for_status()
            data = response.json()

            if "PC_Compounds" not in data:
                return {"error": f"No compound found for '{compound_name}'"}

            compound = data["PC_Compounds"][0]
            cid = compound["id"]["id"]["cid"]

            # Fetch 3D coordinates
            coord_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/JSON?record_type=3d"
            coord_response = requests.get(coord_url)
            coord_response.raise_for_status()
            coord_data = coord_response.json()

            atoms = coord_data["PC_Compounds"][0]["atoms"]
            conformers = coord_data["PC_Compounds"][0]["coords"][0]["conformers"][0]

            # Fetch additional properties
            prop_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,IUPACName,IsomericSMILES/JSON"
            prop_response = requests.get(prop_url)
            prop_response.raise_for_status()

            # Prepare the return dictionary
            return AtomsDict(
                numbers=[atoms["element"][i] for i in range(len(atoms["element"]))],
                positions=list(zip(conformers["x"], conformers["y"], conformers["z"])),
            )
        except requests.exceptions.RequestException as e:
            return {"error": f"An error occurred while fetching data: {str(e)}"}
        except KeyError as e:
            return {"error": f"An error occurred while parsing data: {str(e)}"}
        except Exception as e:
            return {"error": f"An unexpected error occurred: {str(e)}"}
