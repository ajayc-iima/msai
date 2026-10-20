# Use the repo's Windows venv (has uvicorn, litellm, esankhyiki).
# CPU-only; bge-small (~133 MB) downloads on first run and is cached.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AIP_OFFLINE=1 \
    HF_HUB_OFFLINE=0

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir uvicorn sse-starlette fastapi \
       "git+https://github.com/nso-india/mospi-esankhyiki"

COPY aip/ aip/
COPY vidhi/ vidhi/
COPY data/ data/
COPY evaluation/ evaluation/
COPY scripts/ scripts/
COPY tests/ tests/

# Bake the store + warm the embedding index at build time so the first
# request never pays model-load latency.
RUN python scripts/vidhi_build.py \
 && python -c "from vidhi import answer as A; A._get_model()"

EXPOSE 8001
CMD ["python", "-m", "uvicorn", "vidhi.service:app", "--host", "0.0.0.0", "--port", "8001"]
