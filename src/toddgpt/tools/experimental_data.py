import base64
import os
from pathlib import Path
from typing import Union
import requests
from langchain.tools import BaseTool
from pydantic import BaseModel
from typing import Optional
from openai import OpenAI

client = OpenAI()


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


class WavelengthResponse(BaseModel):
    wavelength: float


class MaxWavelengthTool(BaseTool):
    name: str = "max_wavelength_tool"
    description: str = (
        "Use this tool to find the wavelength where maximum absorbance occurs. It takes no path arguments to run."
    )

    def _find_image_url(self, molecule: str):
        links = {
            "cyclobutanone": "https://uv-vis-spectral-atlas-mainz.org/uvvis_data/cross_sections_plots/Organics%20(carbonyls)/Ketones,ketenes/c-C4H6O_lin.jpg"
        }
        return links[molecule]

    def _run(self, molecule: Optional[str] = None, image_url: Optional[str] = None):
        if image_url is None:
            # find image url from resources
            image_url = self._find_image_url(molecule)
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "At what wavelength is the maximum absorbance in this plot?",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"{image_url}",
                            },
                        },
                    ],
                }
            ],
            max_tokens=1000,
            response_format=WavelengthResponse,
            temperature=0.0,
        )
        return response.choices[0]


# Define a custom tool for image processing
# class ImageQuestionTool(BaseTool):
#     name: str = "ImageQuestionTool"
#     description: str = "Use this tool to analyze a plot from experimental data and ask a question about it."

#     def _run(self, image_input: Union[str, Path], question: str):
#         # Load the image from the path or URL
#         if isinstance(image_input, Path) and image_input.exists():
#             base64_image = encode_image(image_input)  # Encode the image to base64

#         response = client.beta.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {"role": "system", "content": "You are a helpful assistant that can analyze experimental data and answer questions about it."},
#                 {"role": "user", "content": question},
#                 {
#                     "role": "user",
#                     "content": [
#                         {"type": "text", "text": question},
#                         {
#                             "type": "image_url",
#                             "image_url": {
#                                 "url": f"data:image/jpeg;base64,{base64_image}"
#                             },
#                         },
#         )

# def _run(self, image_input: Union[str, Path], question: str, model="gpt-4o-mini"):
#     # Load the image from the path or URL
#     if isinstance(image_input, Path) and image_input.exists():
#         base64_image = encode_image(image_input)  # Encode the image to base64

#         headers = {
#             "Content-Type": "application/json",
#             "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
#         }

#         payload = {
#             "model": model,
#             "messages": [
#                 {
#                     "role": "user",
#                     "content": [
#                         {"type": "text", "text": question},
#                         {
#                             "type": "image_url",
#                             "image_url": {
#                                 "url": f"data:image/jpeg;base64,{base64_image}"
#                             },
#                         },
#                     ],
#                 }
#             ],
#             "max_tokens": 300,
#         }

#         response = requests.post(
#             "https://api.openai.com/v1/chat/completions",
#             headers=headers,
#             json=payload,
#         )
#         return response.json()["choices"][0]["message"]["content"]
