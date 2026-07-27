import os
import sys
from dotenv import load_dotenv
from llm import call_model
from history import load_history, save_history
from pathlib import Path
load_dotenv()

CONVERSATIONS_DIR = Path("conversations")
HISTORY_FILE = CONVERSATIONS_DIR / "history.json"

def main():
    if not os.getenv("NVIDIA_API_KEY"):
        print("Error: NVIDIA_API_KEY is not set. check .env file")
        sys.exit(1)

    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    messages = load_history(HISTORY_FILE)
    if messages is None:
        messages = [{"role": "system", "content": "You are a helpful assistant."}]

    print("Chat started. Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user_input.lower() == "quit":
            break
        messages.append({"role": "user", "content": user_input})

        try:
            response = call_model(messages)
            print(f"Assistant: {response}")
            messages.append({"role": "assistant", "content": response})
        except Exception as e:
            print(f"Error: {e}")
            messages.pop()

    save_history(HISTORY_FILE, messages)
    print("Conversation saved.")

if __name__ == "__main__":
    main()
