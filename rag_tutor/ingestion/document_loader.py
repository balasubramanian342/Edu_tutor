"""
document_loader.py

Loads raw college material files (PDF, DOCX, TXT, MD) and returns a
uniform list of page-level records:

    {
        "text": "...",
        "page": 1,
        "source_file": "unit3_recursion.pdf"
    }

Keeping page numbers is important later so a RAG answer can be
traced back to "Unit 3 notes, page 4" instead of just "some document".
"""

from pathlib import Path
from typing import List, Dict


def load_pdf(path: Path) -> List[Dict]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    records = []
    for i, page in enumerate(reader.pages, start=1):
        text = _extract_pdf_page_text(page)
        text = text.strip()
        if text:
            records.append({"text": text, "page": i, "source_file": path.name})
    return records


def _extract_pdf_page_text(page) -> str:
    """
    pypdf's default text extraction ("plain" mode) can drop or merge
    characters on PDFs with certain embedded/subset fonts — e.g. "common"
    coming out as "commn", "operation" as "operati" (missing letters, not
    just bad spacing). This has nothing to do with retrieval or generation
    quality downstream; it's corrupted at the source during ingestion, so
    every chunk built from that text inherits the corruption no matter how
    good the LLM is.

    pypdf's "layout" mode uses a different text-positioning algorithm that
    is often (not always) cleaner on exactly this kind of PDF, so it's
    tried first with a fallback to the default mode for PDFs where layout
    mode isn't supported or raises. This isn't a complete fix — some PDFs
    are corrupted badly enough that no extraction mode recovers the
    original text cleanly, in which case OCR (e.g. pytesseract on rendered
    page images) is the real fix, which is a bigger addition than this
    ingestion pipeline currently does. See FEATURES_AND_ROADMAP.md.
    """
    try:
        text = page.extract_text(extraction_mode="layout") or ""
    except Exception:
        text = ""
    if not text.strip():
        text = page.extract_text() or ""

    # Collapse the excess whitespace layout mode often introduces (it pads
    # text to preserve visual column positions), without touching the
    # actual words/letters.
    import re
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def load_docx(path: Path) -> List[Dict]:
    import docx

    doc = docx.Document(str(path))
    # DOCX has no native "page" concept without rendering the file,
    # so we treat the whole document as page 1 and let the chunker
    # split it further downstream.
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if not full_text.strip():
        return []
    return [{"text": full_text, "page": 1, "source_file": path.name}]


def load_text(path: Path) -> List[Dict]:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []
    return [{"text": text, "page": 1, "source_file": path.name}]


LOADERS = {
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".txt": load_text,
    ".md": load_text,
}


def load_file(path: Path) -> List[Dict]:
    """Dispatch to the right loader based on file extension."""
    ext = path.suffix.lower()
    if ext not in LOADERS:
        raise ValueError(
            f"Unsupported file type '{ext}' for {path.name}. "
            f"Supported: {list(LOADERS.keys())}"
        )
    return LOADERS[ext](path)


def load_directory(input_dir: Path) -> List[Dict]:
    """
    Load every supported file in a directory (recursively) and return
    a single flat list of page records across all files.
    """
    input_dir = Path(input_dir)
    all_records: List[Dict] = []
    skipped: List[str] = []

    for path in sorted(input_dir.rglob("*")):
        if path.is_dir():
            continue
        if path.suffix.lower() not in LOADERS:
            continue
        try:
            records = load_file(path)
            all_records.extend(records)
        except Exception as exc:  # noqa: BLE001 - we want to keep going
            skipped.append(f"{path.name}: {exc}")

    if skipped:
        print(f"[document_loader] Skipped {len(skipped)} file(s) due to errors:")
        for s in skipped:
            print(f"  - {s}")

    return all_records
