# Semantic Search (Lab 3)

A simple semantic search engine that converts text documents into embeddings, retrieves the most relevant documents using cosine similarity, and visualizes the embedding space with PCA.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then edit .env and put your NVIDIA_API_KEY in it
```

## Running

Open `semantic_search_starter.ipynb` and run it top to bottom:

```bash
jupyter notebook semantic_search_starter.ipynb
```

Step 1-2 load the corpus and build the embedding matrix (cache hit on re-runs).
Step 3 runs example queries and prints ranked results.
Step 4 projects the embeddings to 2D with PCA and scatter-plots them, colored
by topic.

## Switching between offline and API mode

Controlled by the `LAB3_EMBEDDING_MODE` environment variable (set in `.env`)

Get the api key and update it in .env file
https://build.nvidia.com/settings/api-keys.


## Understanding the output

### The embedding matrix shape

`embedding_matrix.shape` reports `(number_of_documents, embedding_dimension)`:

- **Rows** = one per document. 25 rows here, one per corpus entry.
- **Columns** = the length of each embedding vector. 

Offline mode produces **64** numbers (the hashed bag-of-words dimension); 
the real API model (`nvidia/nv-embedqa-e5-v5`) returns **1024** numbers.

### The similarity scores

`search()` prints a cosine similarity score per result, always in `[-1, 1]`:

- **1.0** = identical direction (strongly similar).
- **0.0** = orthogonal (no shared meaning).
- **-1.0** = opposite.

### Why offline results sometimes look irrelevant
Offline mode works by matching **shared words**, not meaning.

For example, if we search for **"What is computer science?"**, none of the documents in this corpus contain those exact words. Since the collection only covers topics like astronomy, cooking, sports, music, and history, every document receives a very low score. The top results are therefore mostly random, simply because some hashed word buckets happen to overlap. This is expected behavior of the hashed bag-of-words fallback, not a bug.

When a query contains words that also appear in a document, offline search performs much better. For instance, **"How far does light travel in a year?"** correctly matches the document about light-years because they share key terms.

For true meaning-based search that understands context rather than exact word overlap, switch to API mode, which uses semantic embeddings.

### The PCA projection

The `pca_2d` function first centers the data by subtracting the mean from each feature. It then performs Singular Value Decomposition (SVD) and selects the two directions with the largest singular values, which capture the most variation in the dataset.

The result has the shape **`(number_of_documents, 2)`**, meaning each document is represented by two coordinates: **PC1** and **PC2**. These coordinates are used as the x- and y-axes of the scatter plot.

When the points are colored by topic, documents with similar content should naturally appear close together, forming visible clusters. This makes it easy to see how well the document embeddings separate different topics.

