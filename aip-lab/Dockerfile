# Vidhi Guardian — Statistical Evidence & Validity Firewall
# CPU-only, store baked at build time. No API key required for the
# deterministic path; the optional LLM polish is off by default.
FROM python:3.12-slim

# sentence-transformers needs a compiler for some wheels; keep image small.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first (better layer caching).
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# App code + baked store. Raw PDFs (~150 MB) are excluded via .dockerignore;
# only store.json + excerpts are needed at runtime.
COPY . /app

# Pre-warm the embedding model so the first user query is fast.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

ENV AIP_OFFLINE=0
EXPOSE 7860
CMD ["sh", "-c", "python -m uvicorn vidhi.service:app --host 0.0.0.0 --port ${PORT:-7860}"]
