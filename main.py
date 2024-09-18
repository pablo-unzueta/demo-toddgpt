import os
from src.toddgpt.core import Agent


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
        # Get the question from the user
        conversation = input("Please enter your question (or 'exit' to quit): ")
        # conversation = "Can you help me run a terachem tddft_single_point job on ethylene? "
        # conversation = "What are the major geometric changes after optimizing water? "
        # conversation = "What are the major geometric changes after optimizing glucose? Write the results to a file."

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
        conversation = input("Please enter your question (or 'exit' to quit): ")
        if conversation.lower() == "exit":
            print("Exiting ToddGPT. Goodbye!")
            break


if __name__ == "__main__":
    main()
