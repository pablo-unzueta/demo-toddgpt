from typing import List, Type
from pydantic import BaseModel
from langchain_core.tools import BaseTool
from .datatypes import AtomsDict
from qcio.view import generate_structure_viewer_html
from qcio import Structure


class VisualizationInput(BaseModel):
    data: AtomsDict


class Visualization(BaseTool):
    name: str = "visualization_tool"
    description: str = "Use this tool to visualize the molecule"
    args_schema: Type[BaseModel] = VisualizationInput

    def _run(self, input: VisualizationInput) -> str:
        return self.gen_html(input.data)

    def gen_html(self, data: AtomsDict) -> str:
        return generate_structure_viewer_html(Structure.from_atoms(data))

