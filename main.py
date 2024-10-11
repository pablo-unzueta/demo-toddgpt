import os
from src.toddgpt.core import Agent
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import base64
import re
from PIL import Image
import traceback
import logging
import io

# Set up logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


# Create a custom log handler that captures logs in memory
class MemoryHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs = io.StringIO()

    def emit(self, record):
        log_entry = self.format(record)
        self.logs.write(log_entry + "\n")

    def get_logs(self):
        return self.logs.getvalue()

    def clear(self):
        self.logs.truncate(0)
        self.logs.seek(0)


memory_handler = MemoryHandler()
logging.getLogger().addHandler(memory_handler)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount the static directory
app.mount(
    "/spectra",
    StaticFiles(directory="/Users/pablo/software/demo-toddgpt/public/spectra"),
    name="spectra",
)


class Query(BaseModel):
    text: str
    conversation: list = []


@app.post("/api/query")
async def query(query: Query):
    try:
        logging.info(f"Received query: {query.text}")
        memory_handler.clear()  # Clear previous logs
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")

        agent = Agent("openai", api_key)
        executor = agent.get_executor()

        # Check if this is a follow-up question
        is_follow_up = len(query.conversation) > 0

        if is_follow_up:
            # Prepare the conversation history for follow-up questions
            conversation_history = "\n".join(
                [
                    f"{msg['role']}: {msg['content']}"
                    for msg in query.conversation
                    if "content" in msg
                    and "data:image/png;base64" not in msg.get("content", "")
                ]
            )
            full_query = f"{conversation_history}\nHuman: {query.text}"
        else:
            # For initial questions, just use the query text
            full_query = f"Human: {query.text}"

        logging.debug(f"Prepared full query: {full_query}")

        response = executor.invoke({"conversation": full_query})
        logging.info("Executor invoked successfully")
        logging.debug(f"Executor response: {response}")

        # Check if the response contains an image reference
        def check_image_in_response(response):
            return 'img src="' in response

        has_image = check_image_in_response(response["output"])
        if has_image:
            logging.info("Image detected in response")

            # Function to convert image path to base64
            def get_base64_image(image_path):
                with open(image_path, "rb") as image_file:
                    return base64.b64encode(image_file.read()).decode("utf-8")

            # Function to replace image path with base64 data
            def replace_image_path_with_base64(response, image_processor):
                img_tag_pattern = r'<img\s+src="([^"]+)"'
                matches = re.findall(img_tag_pattern, response)

                for match in matches:
                    img_str = get_base64_image(image_processor(match))
                    base64_src = f"data:image/png;base64,{img_str}"
                    response = response.replace(f'src="{match}"', f'src="{base64_src}"')

                return response

            # Replace image paths with base64 data in the response
            # Resize the image before converting to base64
            def resize_image(image_path, max_size=(300, 300)):
                with Image.open(image_path) as img:
                    img.thumbnail(max_size, Image.LANCZOS)
                    resized_path = f"{os.path.splitext(image_path)[0]}_resized.png"
                    img.save(resized_path, "PNG", quality=95, optimize=True)
                return resized_path

            response["output"] = replace_image_path_with_base64(
                response["output"], image_processor=resize_image
            )

        # Capture logs
        logs = memory_handler.get_logs()

        return {"response": response["output"], "logging": logs}
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        logging.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}\n\nTraceback:\n{traceback.format_exc()}",
        )


@app.get("/api/image")
async def get_image(path: str):
    if os.path.isfile(path):
        return FileResponse(path)
    else:
        raise HTTPException(status_code=404, detail="Image not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


# def main():
#     print("Starting...")

#     # Initialize the Agent with OpenAI API key
#     api_key = os.environ.get("OPENAI_API_KEY")
#     if not api_key:
#         print("OPENAI_API_KEY not found in environment variables.")
#         raise ValueError("Please set the OPENAI_API_KEY environment variable.")

#     agent = Agent("openai", api_key)
#     executor = agent.get_executor()

#     while True:
#         conversation = input("Please enter your question (or 'exit' to quit): ")

#         if conversation.lower() == "exit":
#             print("Exiting ToddGPT. Goodbye!")
#             break

#         # Check if the question mentions a file
#         file_path = None
#         words = conversation.split()
#         for i, word in enumerate(words):
#             if word.endswith(".xyz"):
#                 file_path = word
#                 # Convert the file path to the Docker container path
#                 docker_file_path = os.path.join(
#                     "/app/workdir", os.path.basename(file_path)
#                 )
#                 words[i] = docker_file_path
#                 break

#         # Reconstruct the conversation with the updated file path
#         conversation = " ".join(words)

#         # If a file was mentioned, check if it exists
#         if file_path:
#             if not os.path.exists(docker_file_path):
#                 print(
#                     f"Error: The file {file_path} does not exist in the current directory."
#                 )
#                 continue

#         print(f"Processing conversation: {conversation}")

#         # Run the agent
#         print("Running agent...")
#         result = executor.invoke({"conversation": conversation})

#         # Print the result
#         print("Agent's response:")
#         print(result["output"])
#         print("\n")  # Add a newline for better readability between interactions


# if __name__ == "__main__":
#     main()
