import os
import json
import numpy as np
from embeddings import EMBEDDING_MODE, get_embedding

CACHE_FILE = f"embeddings_cache_{EMBEDDING_MODE}.json"


def load_documents(file_path):
    """Load .json file in and return a list of their contents."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_embedding_matrix(documents):
    """Given a list of documents, return a NumPy matrix of their embeddings.

    One row per document, using whichever embedding mode is active. Embeddings
    are cached to CACHE_FILE so the API is only hit on the first run, or when
    the corpus size or the embedding dimension changes (cache-miss signals).
    """
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached_embeddings = json.load(f)
        except (json.JSONDecodeError, ValueError):
            # Cache file is empty or corrupt (e.g. only partly written, or a
            # leftover file with no content). Treat it as a miss and rebuild.
            cached_embeddings = []
        # Probe the current mode's embedding dimension for one document so we
        # detect a cache written under a different vector size (e.g. a leftover
        # 1024-dim API cache when the query is now 64-dim offline).
        probe_dim = len(get_embedding(documents[0].get("text", ""), input_type="passage"))
        if (
            len(cached_embeddings) == len(documents)
            and len(cached_embeddings[0]) == probe_dim
        ):
            return np.array(cached_embeddings)

    embeddings = [
        get_embedding(doc.get("text", ""), input_type="passage")
        for doc in documents
    ]

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(embeddings, f)

    return np.array(embeddings)


def cosine_similarity(vec1, vec2):
    """Compute the cosine similarity between two vectors."""
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


def search(query, embedding_matrix, documents, top_k):
    """Search for the top_k most similar documents to the given query.
    """
    query_embedding = get_embedding(query, input_type="query")
    similarities = [cosine_similarity(query_embedding, doc_embedding) for doc_embedding in embedding_matrix]
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    top_documents = [(documents[i], similarities[i]) for i in top_indices]
    return top_documents


def pca_2d(X):
    """Perform PCA on the given data matrix X and return the first two principal components."""
    # Center the data
    X_centered = X - np.mean(X, axis=0)
    # Compute SVD
    U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
    # Return the first two principal components
    return U[:, :2] @ np.diag(S[:2])