"""
run_ingestion.py

End-to-end ingestion: raw files -> chunks.json -> vector + BM25 indexes.

Usage:
    python scripts/run_ingestion.py --input data/raw --manifest manifest.json
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.document_loader import load_directory
from ingestion.chunker import load_manifest, build_chunks, save_chunks
from ingestion.build_index import main as build_index_main


def run(input_dir: str, manifest_path: str, output_chunks: str, index_dir: str):
    print(f"== Step 1/3: Loading documents from {input_dir} ==")
    records = load_directory(Path(input_dir))
    print(f"Loaded {len(records)} page record(s)")

    print(f"== Step 2/3: Chunking + tagging metadata (manifest: {manifest_path}) ==")
    manifest = load_manifest(Path(manifest_path))
    chunks = build_chunks(records, manifest)
    save_chunks(chunks, Path(output_chunks))

    print(f"== Step 3/3: Building vector + BM25 indexes ==")
    build_index_main(output_chunks, index_dir)

    print("\nIngestion complete. You can now run scripts/test_retrieval.py to sanity-check retrieval.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run full ingestion pipeline")
    parser.add_argument("--input", default="data/raw")
    parser.add_argument("--manifest", default="manifest.json")
    parser.add_argument("--output-chunks", default="data/processed/chunks.json")
    parser.add_argument("--index-dir", default="data/index")
    args = parser.parse_args()

    run(args.input, args.manifest, args.output_chunks, args.index_dir)
