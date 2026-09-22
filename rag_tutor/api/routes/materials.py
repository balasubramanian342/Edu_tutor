"""
api/routes/materials.py

Lets an instructor add institution course materials (PDF/DOCX/TXT/MD)
through the running app instead of manually editing manifest.json and
running scripts/run_ingestion.py by hand. Saves the file into
data/raw/, updates manifest.json, and re-runs chunking + the BM25
index synchronously (the dense/Chroma index is rebuilt best-effort —
it needs the embedding model, which requires internet access to
Hugging Face the first time; if that's unavailable the upload still
succeeds and BM25 retrieval still works, dense retrieval just won't
reflect the new file until you rebuild it where you do have internet).
"""
import json
import shutil
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from ingestion.document_loader import load_directory, LOADERS
from ingestion.chunker import load_manifest, build_chunks, save_chunks
from ingestion.build_index import build_bm25_index, build_vector_index, load_chunks

router = APIRouter()

RAW_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = ROOT / "manifest.json"
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.json"
INDEX_DIR = ROOT / "data" / "index"


def _load_manifest_dict() -> dict:
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_manifest_dict(manifest: dict) -> None:
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def _reingest() -> dict:
    """Re-runs chunking + BM25 build over everything in data/raw/. Returns a status dict."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    records = load_directory(RAW_DIR)
    manifest = load_manifest(MANIFEST_PATH)
    chunks = build_chunks(records, manifest)
    save_chunks(chunks, CHUNKS_PATH)
    build_bm25_index(chunks, INDEX_DIR / "bm25.pkl")

    dense_status = "skipped"
    try:
        build_vector_index(chunks, INDEX_DIR / "chroma")
        dense_status = "rebuilt"
    except Exception as e:  # noqa: BLE001 - dense index is best-effort here
        dense_status = f"failed ({e.__class__.__name__}: could not load embedding model — " \
                        f"check internet access, then re-run scripts/run_ingestion.py)"

    return {"chunks_built": len(chunks), "sparse_index": "rebuilt", "dense_index": dense_status}


@router.post("/upload")
async def upload_material(
    file: UploadFile = File(...),
    subject: str = Form(...),
    unit: str = Form(...),
    topic: str = Form(...),
    difficulty: str = Form("medium"),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in LOADERS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Supported: {list(LOADERS.keys())}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    manifest = _load_manifest_dict()
    manifest[file.filename] = {
        "subject": subject, "unit": unit, "topic": topic, "difficulty": difficulty,
    }
    _save_manifest_dict(manifest)

    status = _reingest()
    from api.routes.teaching import invalidate_agent_cache
    invalidate_agent_cache()
    return {
        "message": f"'{file.filename}' ingested successfully",
        "filename": file.filename,
        "metadata": manifest[file.filename],
        **status,
    }


@router.get("/")
async def list_materials():
    """Lists ingested files with their topic coverage, derived from the chunk store."""
    if not CHUNKS_PATH.exists():
        return {"files": [], "total_chunks": 0}
    chunks = load_chunks(CHUNKS_PATH)
    by_file = {}
    for c in chunks:
        entry = by_file.setdefault(c["source_file"], {
            "source_file": c["source_file"], "subject": c["subject"], "topics": set(), "chunk_count": 0
        })
        entry["topics"].add(c["topic"])
        entry["chunk_count"] += 1
    files = []
    for entry in by_file.values():
        entry["topics"] = sorted(entry["topics"])
        files.append(entry)
    return {"files": files, "total_chunks": len(chunks)}


@router.delete("/{filename}")
async def remove_material(filename: str):
    """Removes a file from data/raw/ and the manifest, then re-ingests everything else."""
    target = RAW_DIR / filename
    if not target.exists():
        raise HTTPException(404, "File not found in data/raw/")
    target.unlink()

    manifest = _load_manifest_dict()
    manifest.pop(filename, None)
    _save_manifest_dict(manifest)

    status = _reingest()
    from api.routes.teaching import invalidate_agent_cache
    invalidate_agent_cache()
    return {"message": f"'{filename}' removed and materials re-ingested", **status}
