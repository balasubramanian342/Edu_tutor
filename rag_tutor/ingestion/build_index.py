"""
build_index.py

Takes the chunk JSON produced by chunker.py and builds two indexes:

1. A dense vector index (Chroma, persisted to disk) using a
   sentence-transformers embedding model.
2. A sparse BM25 index (rank_bm25, pickled to disk) over the same
   chunk text, for keyword-level matching that embeddings sometimes miss
   (exact terms, formulas, variable names, etc).

These two are combined at query time in retrieval/hybrid_retriever.py.

NOTE: the embedding model is downloaded from Hugging Face the first
time you run this. Make sure the machine running this script has
normal internet access (this is a one-time download, then it's cached
locally).
"""

import json
import pickle
from pathlib import Path
from typing import List, Dict

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"  # small, fast, good enough for a final-year demo


def load_chunks(chunks_path: Path) -> List[Dict]:
    with open(chunks_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_vector_index(chunks: List[Dict], persist_dir: Path) -> None:
    import chromadb
    from sentence_transformers import SentenceTransformer

    persist_dir = Path(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    print(f"[build_index] Loading embedding model '{EMBEDDING_MODEL_NAME}'...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    client = chromadb.PersistentClient(path=str(persist_dir))
    # Fresh collection each build, so re-running ingestion doesn't duplicate chunks
    try:
        client.delete_collection("college_materials")
    except Exception:
        pass
    collection = client.create_collection("college_materials")

    texts = [c["text"] for c in chunks]
    print(f"[build_index] Embedding {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    collection.add(
        ids=[c["chunk_id"] for c in chunks],
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=[
            {
                "source_file": c["source_file"],
                "page": c["page"],
                "subject": c["subject"],
                "unit": c["unit"],
                "topic": c["topic"],
                "difficulty": c["difficulty"],
            }
            for c in chunks
        ],
    )
    print(f"[build_index] Vector index built with {collection.count()} chunks at {persist_dir}")


def build_bm25_index(chunks: List[Dict], output_path: Path) -> None:
    from rank_bm25 import BM25Okapi
    from retrieval.text_utils import tokenize

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tokenized = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized)

    with open(output_path, "wb") as f:
        pickle.dump({"bm25": bm25, "chunks": chunks}, f)

    print(f"[build_index] BM25 index built with {len(chunks)} chunks at {output_path}")


def main(chunks_path: str, index_dir: str):
    chunks_path = Path(chunks_path)
    index_dir = Path(index_dir)

    chunks = load_chunks(chunks_path)
    if not chunks:
        raise ValueError(f"No chunks found in {chunks_path}. Run chunking first.")

    # BM25 first and unconditionally: it has no external dependency (no
    # model download, no network), so it should never be skipped just
    # because the dense step below fails. Previously this ran dense-first
    # with no error handling, so a failed embedding-model download (no
    # internet, firewalled network, etc.) meant BM25 never got built
    # either — leaving retrieval with nothing at all, even though BM25
    # alone would have worked fine.
    build_bm25_index(chunks, index_dir / "bm25.pkl")

    try:
        build_vector_index(chunks, index_dir / "chroma")
    except Exception as e:  # noqa: BLE001
        print(
            f"\n[build_index] Dense (vector) index build failed: {e}\n"
            "[build_index] This usually means the embedding model couldn't be "
            "downloaded from Hugging Face (check internet access / firewall). "
            "BM25 sparse retrieval was still built successfully above and will "
            "work on its own — dense retrieval will activate automatically "
            "once you can re-run this script with internet access.\n"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build dense + sparse indexes from chunk JSON")
    parser.add_argument("--chunks", default="data/processed/chunks.json")
    parser.add_argument("--index-dir", default="data/index")
    args = parser.parse_args()

    main(args.chunks, args.index_dir)
