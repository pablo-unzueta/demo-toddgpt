import os
import base64
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional

class GrabImageInput(BaseModel):
    path: str = Field(..., description="Path to the image file")

class GrabImage(BaseTool):
    name: str = "GrabImage"
    description: str = "Grabs an image and returns its base64 encoding"
    args_schema: Type[BaseModel] = GrabImageInput

    def _run(self, path: str) -> str:
        if path.startswith("__FRONTEND_IMAGE__"):
            return path

        # Check if the image_path is already in the public directory
        if not path.startswith("public/generated_images/"):
            # If not, save the image to the public directory
            with open(path, "rb") as image_file:
                image_data = image_file.read()

            # Generate a unique filename
            filename = f"generated_image_{os.path.basename(path)}"
            new_path = f"public/generated_images/{filename}"

            with open(new_path, "wb") as new_file:
                new_file.write(image_data)

            path = new_path

        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    async def _arun(self, path: str) -> str:
        # Implement async version if needed
        return self._run(path)

if __name__ == "__main__":
    tool = GrabImage()
    print(tool.run("/Users/pablo/software/demo-toddgpt/public/spectra/logo.base64"))
