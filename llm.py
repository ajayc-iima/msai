import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "meta/llama-3.1-8b-instruct"

def call_model(messages):
    api_key = os.getenv("NVIDIA_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    data = {"model": MODEL, "messages": messages}

    try:
        response = requests.post(API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Could not connect to the API. Check your internet connection.")
    except requests.exceptions.Timeout:
        raise TimeoutError("Request timed out.")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"API error {e.response.status_code}: {e.response.text[:200]}")
