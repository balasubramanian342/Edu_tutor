"""
test_retrieval.py

Quick manual sanity check for retrieval quality. Run this after
run_ingestion.py to confirm the right chunks come back for a few
sample questions before you build the generation layer on top.

Usage:
    python scripts/test_retrieval.py "What is a base case in recursion?"
    python scripts/test_retrieval.py "Explain merge sort" --gap-topic Sorting
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.hybrid_retriever import HybridRetriever, format_context_for_llm


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test hybrid retrieval")
    parser.add_argument("query", type=str)
    parser.add_argument("--gap-topic", default=None)
    parser.add_argument("--subject", default=None)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--index-dir", default="data/index")
    args = parser.parse_args()

    retriever = HybridRetriever(index_dir=args.index_dir)
    results = retriever.retrieve(
        args.query, top_k=args.top_k, gap_topic=args.gap_topic, subject=args.subject
    )

    print(f"\nQuery: {args.query}")
    print(f"Gap topic bias: {args.gap_topic}\n")
    print("=" * 60)
    for i, c in enumerate(results, start=1):
        print(f"[{i}] score={c['_score']:.3f} | {c['source_file']} p.{c['page']} | topic={c['topic']}")
        print(f"    {c['text'][:150]}...")
        print("-" * 60)

    print("\nFormatted context block (this is what gets passed to the LLM prompt):\n")
    print(format_context_for_llm(results))


if __name__ == "__main__":
    main()
