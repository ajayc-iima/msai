# API Explorer Chatbot

A command-line chatbot that talks to NVIDIA's Llama 3.1 8B Instruct model via the NIM API.

## How to Run

1. Create a `.env` file with your API key:
   ```
   NVIDIA_API_KEY="nvapi-your-key-here"
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the chatbot:
   ```
   python chatbot.py
   ```
4. Type `quit` to exit. Conversations automatically save and resume across sessions.
