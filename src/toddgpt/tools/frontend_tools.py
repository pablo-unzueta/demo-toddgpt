from pydantic import BaseModel
from langchain_core.tools import BaseTool
from typing import Type
import base64


class GrabImageInput(BaseModel):
    path: str


class GrabImage(BaseTool):
    name: str = "grab_image"
    description: str = (
        "Use this tool to grab an image and send it as base64 encoded string."
    )
    args_schema: Type[BaseModel] = GrabImageInput

    def _run(self, path: str):
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
