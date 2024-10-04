import os
from src.toddgpt.core import Agent
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

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
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")

        agent = Agent("openai", api_key)
        executor = agent.get_executor()

        # Prepare the conversation history
        conversation_history = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in query.conversation]
        )

        # Add the current query to the conversation
        full_query = f"{conversation_history}\nHuman: {query.text}"

        response = executor.invoke({"conversation": full_query})
        return {"response": response["output"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/image")
async def get_image(path: str):
    if os.path.isfile(path):
        return FileResponse(path)
    else:
        raise HTTPException(status_code=404, detail="Image not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


def main():
    print("Starting...")

    # Initialize the Agent with OpenAI API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not found in environment variables.")
        raise ValueError("Please set the OPENAI_API_KEY environment variable.")

    agent = Agent("openai", api_key)
    executor = agent.get_executor()

    while True:
        conversation = input("Please enter your question (or 'exit' to quit): ")

        if conversation.lower() == "exit":
            print("Exiting ToddGPT. Goodbye!")
            break

        # Check if the question mentions a file
        file_path = None
        words = conversation.split()
        for i, word in enumerate(words):
            if word.endswith(".xyz"):
                file_path = word
                # Convert the file path to the Docker container path
                docker_file_path = os.path.join(
                    "/app/workdir", os.path.basename(file_path)
                )
                words[i] = docker_file_path
                break

        # Reconstruct the conversation with the updated file path
        conversation = " ".join(words)

        # If a file was mentioned, check if it exists
        if file_path:
            if not os.path.exists(docker_file_path):
                print(
                    f"Error: The file {file_path} does not exist in the current directory."
                )
                continue

        print(f"Processing conversation: {conversation}")

        # Run the agent
        print("Running agent...")
        result = executor.invoke({"conversation": conversation})

        # Print the result
        print("Agent's response:")
        print(result["output"])
        print("\n")  # Add a newline for better readability between interactions


if __name__ == "__main__":
    main()
