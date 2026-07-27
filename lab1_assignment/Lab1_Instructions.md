# Lab 1 — The API Explorer

Build a command-line chatbot that talks to a real LLM API, holds a conversation, and remembers that conversation across restarts.

Work in this `api_explorer/` folder. It already has the empty files you'll fill in (`chatbot.py`, `llm.py`, `history.py`, `requirements.txt`, `README.md`, `.env`) plus a `conversations/` folder for saved chat history.

---

## 0. Before You Touch Any Code: Get an API Key

This lab uses **NVIDIA NIM**, accessed through NVIDIA's OpenAI-compatible endpoint.

1. Go to [build.nvidia.com](https://build.nvidia.com) and create a free account. You will need to **verify your phone number** as part of signup — do this before lab day if you can, it takes a few extra minutes.
2. Go to [build.nvidia.com/settings/api-keys](https://build.nvidia.com/settings/api-keys) and generate a key. It will start with `nvapi-`.
3. **Never paste your key directly into a `.py` file.** Set it as an environment variable, or put it in a `.env` file (there's already an empty one in this folder) like this:
   ```
   NVIDIA_API_KEY="nvapi-your-key-here"
   ```
   and load it with `python-dotenv`. Hard-coding secrets is exactly the habit we've been telling you to avoid since L2 — this lab is where it actually matters.

Key facts you'll need:
- **Endpoint:** `https://integrate.api.nvidia.com/v1/chat/completions`
- **Auth header:** `Authorization: Bearer <NVIDIA_API_KEY>`
- **Model:** `meta/llama-3.1-8b-instruct`
- Request/response shape is the standard OpenAI-style `messages` list — the same `{"role": ..., "content": ...}` format from lecture. Nothing new to learn there.

The free tier is rate-limited, not a hard quota — occasional `429` errors under load are normal and something you'll handle in Stage 5, not a sign something's broken.

---

## 1. Prove the Connection Works First

Don't write the full program yet. Write the smallest possible script: send one hard-coded message to the API and print the reply. If you can get a real response back, your key, network, and request format are all confirmed working — everything after this is just structure built on top of a call you already know works.

Also print the *raw* response object once, before you extract just the text, so you understand the full shape you're pulling `choices[0].message.content` out of.

If this doesn't work, stop and debug it here. Don't build the rest of the lab on top of a broken connection — see the troubleshooting tips at the end of this doc.

## 2. Wrap the Call in a Function

Turn your working script into a function that takes a full list of messages and returns the assistant's reply text.

Important detail: the function should take the **entire conversation so far**, not just the newest message. There is no memory on the server side — the model only "remembers" earlier turns because you resend the whole history every time. Understanding that now will save you confusion later.

## 3. Build the Live Conversation Loop

Now build the actual chat loop:
- Print a prompt, read user input.
- If the user types `quit`, stop.
- Otherwise, add their message to the conversation, call the model, add the reply to the conversation, print it, and loop.

At the end of this stage you should have a working chatbot — but it forgets everything the moment the program exits. That's the problem the next stage solves.

## 4. Add Persistence (Load on Start, Save on Quit)

- On startup, load a saved conversation from a JSON file in `conversations/` if one exists; otherwise start a fresh conversation with a system prompt.
- On quit, save the full conversation back to that file.

**Test this yourself, live:** run the program, have a short conversation, quit, run it again, and confirm it picks up where you left off. This is the single most convincing proof that your program actually works — don't skip actually doing it.

---

## 5. Error Handling — Four Required Targets

This is where most of the lab's grading weight sits (see rubric below). Your program needs to fail *gracefully*, with a readable message, not crash with a raw traceback, for each of these:

1. **Missing or invalid API key.** Check for the key before anything else runs, and exit immediately with a clear message if it's missing.
2. **Dropped connection, timeout, or API error response** (including rate limits). A failed call during a conversation shouldn't crash the whole program — the user should see a readable error and be able to keep chatting.
3. **Corrupted or missing conversation JSON file on load.** If the saved file can't be parsed, don't crash — warn the user and start a fresh conversation instead.
4. **Empty user input.** If someone hits Enter without typing anything, re-prompt instead of sending an empty message to the API.

A subtle thing to think about: what should happen to the conversation history if a call fails partway through a turn? If you've already added the user's message to the list before the call fails, think about whether that message should stay in the history or be removed — test what your saved JSON looks like after a failure and see if it reads sensibly.

**Test all four yourself before you submit:**
- Unset your `NVIDIA_API_KEY` and run the program — should fail with a clear message, not a traceback.
- Disconnect your wifi mid-conversation — should print a readable error and let you keep going.
- Hand-edit `conversations/history.json` into invalid JSON and launch — should start fresh with a warning, not crash.
- Press Enter on an empty prompt — should re-prompt, not call the API.

## 6. Organize Into Multiple Files (Optional but Recommended)

Split your single `chatbot.py` into:
- `llm.py` — the API call function
- `history.py` — load/save functions
- `chatbot.py` — the entry point and main loop, importing from the other two

This isn't a rubric requirement — a single well-organized `chatbot.py` with clean functions is a fully acceptable submission. But splitting things up is good practice and worth doing if you have time.

## 7. Stretch Goals (Optional)

Add command-line flags using `argparse`:
- `--system "..."` — set a custom system prompt for a new conversation
- `--load path/to/file.json` — resume a specific saved conversation
- `--save path/to/file.json` — save to a specific file instead of the default

These are extra practice only. Not having them will not cost you marks on the core lab.

---

## Deliverable Checklist

- [ ] Working `chatbot.py`, runnable from the command line
- [ ] A saved conversation JSON file as proof it works
- [ ] A `README.md` explaining what your program does and how to run it
- [ ] Code organized into functions — no single giant block
- [ ] All four error-handling targets demonstrably handled

## Grading Rubric (Lab 1 = 5% of course grade)

| Category | Weight | What's checked |
|---|---|---|
| Core functionality | 60% | Live conversation loop calling the real API (30%) + persistence: saves on exit, correctly reloads and continues on a fresh run (30%). Graded as working / not working, not partial credit. |
| Error handling | 25% | Split evenly across the four targets above (~6% each). Credit for "fails gracefully with a useful message," not just "doesn't crash." |
| Code organization | 10% | Some separation of concerns — not one giant function. A single well-organized `chatbot.py` is sufficient; splitting into multiple files (Stage 6) is not required for full credit. |

---

## How to Submit

1. Push your final code to a **GitHub repository** with an appropriate name. Make sure the repository is **public** so it can be reviewed.
2. Your repo should include at minimum: `chatbot.py`, `requirements.txt`, a `README.md`, and a `.gitignore` that excludes your `.env` file (never commit your API key).
3. Submit the **link to your public GitHub repository** on Moodle. That link is your submission — nothing else needs to be uploaded separately.

Before you submit, double check: does the repo actually build and run if someone clones it fresh (with their own API key)? A repo that only works on your machine because of local state isn't a complete submission.

---

## Troubleshooting Quick Reference

| Symptom | Likely cause | Fix |
|---|---|---|
| Program exits immediately saying no key found | `NVIDIA_API_KEY` not set in this terminal, or `.env` not being loaded | Re-export it, or confirm your `.env` loading code actually runs before anything else |
| `401` / `403` from the API | Key has extra whitespace, phone verification incomplete, or key revoked | Confirm phone verification finished at build.nvidia.com, then regenerate the key |
| `429` Too Many Requests | Free-tier rate limit — can happen under load even with light individual use | Wait a moment and retry; this should already be caught by your error handling |
| `ConnectionError` | No internet, or network blocking the endpoint | Check connectivity; try a phone hotspot as a fallback |
| Crash on loading `history.json` | File is empty or hand-edited incorrectly | Should be caught by your Stage 5 error handling — if it crashes raw, you're missing that guard |
| Chatbot "forgets" everything every run | Load/save not wired up, or writing to a different path each time | Print the resolved file path on save and load so you can see exactly which file is in use |
| `KeyError` on `choices[0]` or an empty response | Malformed request body, or the model name has changed | Print the raw response JSON to inspect it; check build.nvidia.com for the current model ID |
