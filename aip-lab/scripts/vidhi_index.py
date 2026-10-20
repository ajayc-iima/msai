#!/usr/bin/env python3
"""vidhi corpus index: all lab PDFs -> chunks -> passage vectors (Lab 3).

One-time build (rerun when data/raw changes; manifest pins sha256).
Serving loads the .npy matrix -- no re-encoding, ever.

    python scripts/vidhi_index.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aip.chunking import sliding_chunks

PDFS = [
    "mospi_HCES_2023-24_Factsheet.pdf",
    "mospi_HCES_2023-24_PressNote_30012025.pdf",
    "mospi_HCES_2023-24_FinalReport.pdf",
    "mospi_PLFS_2023-24_AnnualReport.pdf",
    "mospi_PLFS_2025_F_REV_29052026.pdf",
    "mospi_PLFS_Changes-in-2025_rev.pdf",
    "microdata_DDI-IND-NSO-TUS-2024-24__Vol_II_TUS_2024.pdf",
]
OUT = ROOT / "vidhi" / "index"


def main() -> int:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    import numpy as np
    from sentence_transformers import SentenceTransformer

    OUT.mkdir(parents=True, exist_ok=True)
    chunks = []
    manifest: dict = {"pdfs": []}
    for pdf in PDFS:
        raw = (ROOT / "data" / "raw" / pdf).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        text = "\n".join(pg.get_text() for pg in fitz.open(ROOT / "data" / "raw" / pdf))
        made = sliding_chunks(text, pdf, size=800, overlap=150)
        chunks.extend(made)
        manifest["pdfs"].append(
            {"pdf": pdf, "sha256": sha, "chars": len(text), "chunks": len(made)}
        )
        print(f"{pdf}: {len(text)} chars -> {len(made)} chunks")
    model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    vecs = model.encode(
        [c.text for c in chunks],
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=64,
    )
    np.save(OUT / "vectors.npy", np.asarray(vecs, dtype="float32"))
    with (OUT / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(
                json.dumps({"doc_id": c.chunk_id, "pdf": c.doc_id, "text": c.text})
                + "\n"
            )
    manifest.update(
        {
            "n_chunks": len(chunks),
            "dim": int(vecs.shape[1]),
            "model": "BAAI/bge-small-en-v1.5 (passage)",
        }
    )
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"index: {len(chunks)} chunks -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

