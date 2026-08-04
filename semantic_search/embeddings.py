"""Embedding fetching for your semantic search system.

Two modes, controlled by the LAB3_EMBEDDING_MODE environment variable:

    "offline" (default) - a hashed bag-of-words vector. Fully implemented
                below already - you don't need to write or even fully
                understand this part, it's provided so you can build and
                test your whole pipeline with no API key and no network.
    "api"     - calls NVIDIA NIM's embeddings endpoint. THIS is the part
                you implement - see get_embedding() below.

Both modes return a plain Python list of floats, so the rest of your code
never needs to know which one is in use.
"""

import hashlib
import math
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()  # picks up NVIDIA_API_KEY and LAB3_EMBEDDING_MODE from a .env file, if present

EMBEDDING_MODE = os.environ.get("LAB3_EMBEDDING_MODE", "offline")  # "api" or "offline"

API_KEY = os.environ.get("NVIDIA_API_KEY")
EMBEDDING_MODEL = "nvidia/nv-embedqa-e5-v5"
EMBEDDING_URL = "https://integrate.api.nvidia.com/v1/embeddings"

OFFLINE_DIM = 64
_WORD_RE = re.compile(r"[a-z']+")


# --- Provided for you: don't need to modify this ---------------------------
def _get_embedding_offline(text, dim=OFFLINE_DIM):
    """A deterministic hashed bag-of-words vector - no model, no network.

    Each word hashes into one of `dim` buckets and increments a count there.
    The result is L2-normalized so cosine similarity behaves sensibly.
    Documents that share vocabulary land close together, which is enough to
    test the full search + visualization pipeline offline. This is a real,
    historically-used text representation technique (not a random stub) -
    it just isn't a semantic embedding, so don't expect meaning-based
    matches from it. Swap to API mode for that.
    """
    vec = [0.0] * dim
    words = _WORD_RE.findall(text.lower())
    for word in words:
        bucket = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % dim
        vec[bucket] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec
# -----------------------------------------------------------------------


def _get_embedding_api(text, input_type="passage"):
    """TODO: implement this.

    Call NVIDIA NIM's embeddings endpoint (same pattern as Lab 1's chat
    completions call - check for a key, POST with the right headers/body,
    handle the response) and return the embedding as a plain list of floats.

    Two things that are DIFFERENT from Lab 1's chat endpoint - read the
    NIM API docs / Lab3_Instructions.md before assuming the shape:
      - `input` in the request body must be a LIST of strings, not a bare string.
      - this model needs an `input_type` field: "passage" for documents you're
        indexing, "query" for the search query itself.
    """

    if not API_KEY:
        raise ValueError(
            "NVIDIA_API_KEY environment variable is not set. "
            "Please set it to your NVIDIA NIM API key."
        )
    data = {
        "model": EMBEDDING_MODEL,
        "input": [text],
        "input_type": input_type,
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }   
    try:
        print(f"Fetching embedding using NVIDIA NIM API for input_type='{input_type}'...")
        response = requests.post(EMBEDDING_URL, headers=headers, json=data)
        response.raise_for_status()
        embedding = response.json()["data"][0]["embedding"]
        return embedding
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error fetching embedding from NVIDIA NIM API: {e}")   



def get_embedding(text, input_type="passage"):
    if EMBEDDING_MODE == "api":
        return _get_embedding_api(text, input_type=input_type)
    return _get_embedding_offline(text)
