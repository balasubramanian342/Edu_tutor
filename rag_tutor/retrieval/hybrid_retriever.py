"""
hybrid_retriever.py

Combines dense (vector) and sparse (BM25) retrieval using Reciprocal
Rank Fusion (RRF), then reranks the fused candidates with a
cross-encoder for the final ordering.

Why hybrid + rerank instead of just dense search:
- Dense embeddings are great at semantic similarity but can miss exact
  keyword matches (e.g. a specific formula name, variable, or term).
- BM25 is great at exact keyword matches but misses paraphrases.
- RRF combines both rankings without needing to tune score weights.
- A cross-encoder reranker looks at the (query, chunk) pair jointly,
  which is more accurate than comparing two independent embeddings,
  at the cost of being slower — which is why we only rerank the top
  candidates from the fused list, not the whole corpus.

This module also supports "gap-aware" retrieval: if a topic is passed
in (from your gap analysis module), matching chunks are boosted so the
agent is more likely to teach the actual prerequisite gap, not just
whatever is textually closest to the raw student question.
"""

import pickle
from pathlib import Path
from typing import List, Dict, Optional

from retrieval.text_utils import tokenize


class HybridRetriever:
    def __init__(
        self,
        index_dir: str = "data/index",
        embedding_model_name: str = "all-MiniLM-L6-v2",
        reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ):
        index_dir = Path(index_dir)

        # BM25 has no external dependency (no model download, no network),
        # so it's loaded first and unconditionally — if this fails, there's
        # genuinely no index to serve from and the caller should fall back
        # to NullRetriever. Everything below this is best-effort: dense
        # search and reranking both need to download models from Hugging
        # Face, which can fail (no internet, firewall, first-run delay).
        # Previously any failure anywhere in this constructor — including
        # just the embedding model download — aborted retrieval entirely,
        # discarding a perfectly good BM25 index in the process. Now a
        # dense/reranker failure only disables that specific capability;
        # BM25 keeps working on its own.
        print("[HybridRetriever] Loading BM25 index...")
        with open(index_dir / "bm25.pkl", "rb") as f:
            bm25_data = pickle.load(f)
        self.bm25 = bm25_data["bm25"]
        self.bm25_chunks = bm25_data["chunks"]  # same order used to build BM25
        self.chunk_by_id = {c["chunk_id"]: c for c in self.bm25_chunks}

        self.dense_available = False
        self.rerank_available = False

        try:
            import chromadb
            print("[HybridRetriever] Loading vector index...")
            client = chromadb.PersistentClient(path=str(index_dir / "chroma"))
            self.collection = client.get_collection("college_materials")

            from sentence_transformers import SentenceTransformer
            print("[HybridRetriever] Loading embedding model...")
            self.embed_model = SentenceTransformer(embedding_model_name)
            self.dense_available = True
        except Exception as e:  # noqa: BLE001
            print(f"[HybridRetriever] Dense retrieval unavailable ({e}); continuing with BM25-only search.")

        try:
            from sentence_transformers import CrossEncoder
            print("[HybridRetriever] Loading reranker model...")
            self.reranker = CrossEncoder(reranker_model_name)
            self.rerank_available = True
        except Exception as e:  # noqa: BLE001
            print(f"[HybridRetriever] Reranker unavailable ({e}); ranking by fused/BM25 score instead.")

    def _dense_search(self, query: str, k: int) -> List[str]:
        """Returns a ranked list of chunk_ids from vector search."""
        query_emb = self.embed_model.encode([query], convert_to_numpy=True).tolist()
        results = self.collection.query(query_embeddings=query_emb, n_results=k)
        return results["ids"][0]

    def _sparse_search(self, query: str, k: int) -> List[str]:
        """Returns a ranked list of chunk_ids from BM25 search."""
        return [cid for cid, _ in self._sparse_search_scored(query, k)]

    def _sparse_search_scored(self, query: str, k: int):
        """Same as _sparse_search but keeps the raw BM25 score per chunk_id."""
        tokenized_query = tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self.bm25_chunks[i]["chunk_id"], float(scores[i])) for i in ranked_indices]

    @staticmethod
    def _reciprocal_rank_fusion(
        ranked_lists: List[List[str]], k: int = 60
    ) -> List[str]:
        """
        Standard RRF: score(doc) = sum over lists of 1 / (k + rank_in_list).
        k=60 is the commonly used constant from the original RRF paper;
        it just dampens the impact of any single list's top rank.
        """
        scores: Dict[str, float] = {}
        for ranked_list in ranked_lists:
            for rank, chunk_id in enumerate(ranked_list):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
        return sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    def retrieve(
        self,
        query: str,
        top_k: int = 4,
        fusion_candidates: int = 15,
        gap_topic: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> List[Dict]:
        """
        Main entry point. Returns the top_k chunks (with metadata) most
        relevant to `query`, optionally biased toward `gap_topic` (the
        root gap identified by the gap-analysis module) and filtered to
        a `subject` if given.
        """
        dense_ids = self._dense_search(query, k=fusion_candidates) if self.dense_available else []
        sparse_scored = self._sparse_search_scored(query, k=fusion_candidates)
        sparse_ids = [cid for cid, _ in sparse_scored]
        sparse_score_by_id = dict(sparse_scored)
        fused_ids = self._reciprocal_rank_fusion([dense_ids, sparse_ids]) if dense_ids else sparse_ids

        candidates = [self.chunk_by_id[cid] for cid in fused_ids if cid in self.chunk_by_id]

        if subject:
            candidates = [c for c in candidates if c["subject"].lower() == subject.lower()] or candidates

        if not candidates:
            return []

        if self.rerank_available:
            # Cross-encoder rerank on the fused candidate set
            pairs = [[query, c["text"]] for c in candidates]
            rerank_scores = self.reranker.predict(pairs)
        else:
            # No reranker available — score by the real BM25 match strength
            # (normalized 0-1 by the strongest score among candidates),
            # NOT by rank position. Rank position alone was a real bug: it
            # produced a confident-looking descending score curve (e.g.
            # 1.0, 0.86, 0.71...) even when every candidate had a genuine
            # BM25 score of 0 — i.e. the query term didn't actually appear
            # anywhere in the corpus. That showed up as ~88% confidence on
            # an answer built from completely unrelated content. Now a
            # true no-match correctly collapses every score to 0, which
            # flows into _calculate_confidence() and correctly triggers
            # the "insufficient information" / requires-review path
            # instead of confidently citing the wrong topic.
            max_score = max((sparse_score_by_id.get(c["chunk_id"], 0.0) for c in candidates), default=0.0)
            if max_score == 0.0:
                # Genuinely nothing in the corpus matched this query at
                # all (every BM25 score is 0) — return no results rather
                # than the fused/BM25 tie-break order's arbitrary "top"
                # pick, so the caller (explanation_generator.py) correctly
                # falls back to "I don't have sufficient information..."
                # instead of confidently explaining an unrelated topic.
                return []
            rerank_scores = [sparse_score_by_id.get(c["chunk_id"], 0.0) / max_score for c in candidates]

        # Build fresh result dicts rather than mutating the cached chunk
        # objects in self.chunk_by_id / self.bm25_chunks — those are shared
        # across every call, so writing a score onto them directly would
        # leak state between queries.
        results = []
        for c, score in zip(candidates, rerank_scores):
            # Soft boost if this chunk matches the identified learning gap topic —
            # this is what makes retrieval "gap-aware" rather than purely
            # query-similarity-driven.
            boost = 0.15 if gap_topic and c["topic"].lower() == gap_topic.lower() else 0.0
            results.append(
                {
                    "chunk_id": c["chunk_id"],
                    "text": c["text"],
                    "score": float(score) + boost,
                    # Nested under 'metadata' to match the contract expected
                    # by agent/teaching_agent.py and agent/explanation_generator.py
                    "metadata": {
                        "source_file": c["source_file"],
                        "page": c["page"],
                        "subject": c["subject"],
                        "unit": c["unit"],
                        "topic": c["topic"],
                        "difficulty": c["difficulty"],
                    },
                }
            )

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]


def format_context_for_llm(chunks: List[Dict]) -> str:
    """
    Formats retrieved chunks into a citation-ready context block to pass
    into the generation prompt. Each chunk is labeled so the LLM can
    cite "[Source 2]" etc, and you can map that back to the real file/page.
    """
    lines = []
    for i, c in enumerate(chunks, start=1):
        meta = c.get("metadata", {})
        lines.append(
            f"[Source {i}] ({meta.get('source_file', 'unknown')}, "
            f"page {meta.get('page', '?')}, topic: {meta.get('topic', 'unknown')})\n{c['text']}\n"
        )
    return "\n".join(lines)


class NullRetriever:
    """
    Drop-in stand-in for HybridRetriever when the real one can't load
    (no vector index built yet, or no internet access to download the
    embedding/reranker models). Always returns no results.

    This lets TeachingAgent (agent/teaching_agent.py) run unconditionally
    against a retriever object without the API layer needing an
    `if retriever:` branch everywhere it's used — ExplanationGenerator
    already handles an empty chunk list gracefully ("I don't have
    sufficient information in the course materials..."), so the system
    degrades cleanly instead of crashing.
    """

    def retrieve(self, query: str, top_k: int = 4, gap_topic=None, subject=None) -> List[Dict]:
        return []
