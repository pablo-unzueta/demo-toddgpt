import pytest
from src.toddgpt.tools.frontend_tools import GrabImage
import base64
import os

@pytest.fixture
def sample_image(tmp_path):
    image_path = tmp_path / "test_image.png"
    with open(image_path, "wb") as f:
        f.write(b"fake image data")
    return str(image_path)

def test_grab_image(sample_image):
    grab_image_tool = GrabImage()
    result = grab_image_tool._run(sample_image)
    
    assert isinstance(result, str)
    assert base64.b64decode(result) == b"fake image data"

def test_grab_image_nonexistent_file():
    grab_image_tool = GrabImage()
    with pytest.raises(FileNotFoundError):
        grab_image_tool._run("nonexistent_file.png")

def test_grab_image_empty_file(tmp_path):
    empty_file = tmp_path / "empty.png"
    empty_file.touch()
    
    grab_image_tool = GrabImage()
    result = grab_image_tool._run(str(empty_file))
    
    assert result == base64.b64encode(b"").decode("utf-8")
