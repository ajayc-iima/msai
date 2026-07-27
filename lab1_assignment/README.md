# API Explorer Chatbot

A command-line chatbot that talks to NVIDIA's Llama 3.1 8B Instruct model via the NIM API. It holds a conversation, remembers the full history, and saves/loads conversations across restarts.

## How to Run

1. Create a `.env` file with your NVIDIA NIM API key:
   ```
   NVIDIA_API_KEY="nvapi-your-key-here"
   ```
   Get a free key at https://build.nvidia.com/settings/api-keys

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the chatbot:
   ```
   python chatbot.py
   ```

4. Type `quit` to exit. Conversations automatically save to `conversations/history.json` and resume when you run the program again.

## What It Does

- Sends your messages to the LLM and prints the assistant's reply
- Sends the **full conversation history** on every request so the model remembers context
- Loads the previous conversation on startup and saves on quit
- Handles errors gracefully: missing API key, network failures, rate limits, corrupted save files, and empty input

## Files

- `chatbot.py` — entry point and main conversation loop
- `llm.py` — API call function with error handling
- `history.py` — load and save conversation history
- `requirements.txt` — dependencies (`requests`, `python-dotenv`)
- `conversations/history.json` — saved conversation (auto-generated)
