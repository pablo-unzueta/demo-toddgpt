from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI()

# Mount the static directory
app.mount(
    "/spectra",
    StaticFiles(directory="/Users/pablo/software/demo-toddgpt/public/spectra"),
    name="spectra",
)


@app.get("/api/image")
async def get_image(path: str):
    if os.path.isfile(path):
        return FileResponse(path)
    else:
        raise HTTPException(status_code=404, detail="Image not found")
