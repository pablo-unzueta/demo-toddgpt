import os
from src.toddgpt.core import Agent
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


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


app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Add your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Query(BaseModel):
    text: str


@app.post("/api/query")
async def query_agent(query: Query):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables.")
    
    agent = Agent("openai", api_key)
    executor = agent.get_executor()
    result = executor.invoke({"conversation": query.text})
    return {"response": result["output"]}
