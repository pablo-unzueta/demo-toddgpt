import os
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type


class GrabImageInput(BaseModel):
    path: str = Field(..., description="Path to the image file")


class GrabImage(BaseTool):
    name: str = "GrabImage"
    description: str = "Grabs an image and returns its path for frontend rendering"
    args_schema: Type[BaseModel] = GrabImageInput

    def _run(self, path: str) -> str:
        if path.startswith("__FRONTEND_IMAGE__"):
            return path

        # Adjust the path to point to the root public directory
        root_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        public_dir = os.path.join(root_dir, "public")

        if not path.startswith(public_dir):
            # If not, save the image to the public directory
            with open(path, "rb") as image_file:
                image_data = image_file.read()

            # Generate a unique filename
            filename = f"{os.path.basename(path)}"
            new_path = os.path.join(public_dir, filename)

            with open(new_path, "wb") as new_file:
                new_file.write(image_data)

            path = new_path

        # Return the path relative to the public directory
        return os.path.relpath(path, start=public_dir)

    async def _arun(self, path: str) -> str:
        # Implement async version if needed
        return self._run(path)


if __name__ == "__main__":
    tool = GrabImage()
    print(tool.run("/Users/pablo/software/demo-toddgpt/public/spectra/logo.base64"))
