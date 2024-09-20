from src.toddgpt.tools.experimental_data import MaxWavelengthTool
import pytest
from pathlib import Path


@pytest.mark.parametrize(
    "image_url",
    [
        (
            "https://uv-vis-spectral-atlas-mainz.org/uvvis_data/cross_sections_plots/Organics%20(carbonyls)/Ketones,ketenes/c-C4H6O_lin.jpg"
        ),
    ],
)
def test_max_wavelength_tool(image_url):
    tool = MaxWavelengthTool()
    response = tool._run(image_url=image_url)
    print(response)


def test_max_wavelength_tool_no_image_url():
    tool = MaxWavelengthTool()
    response = tool._run(molecule="cyclobutanone")
    print(response)
