"""
chunker.py

Splits page-level text into overlapping word-based chunks and attaches
metadata (subject, unit, topic, difficulty) so retrieval can later be
filtered/boosted by topic, not just by raw text similarity.

Metadata comes from a manifest.json that maps a source filename (or a
glob-style prefix) to its subject/unit/topic/difficulty. This keeps
tagging explicit and reviewable, rather than trying to auto-guess
topics from filenames (which is unreliable for a final-year project
demo where accuracy matters more than automation).

Example manifest.json:
{
    "unit3_recursion.pdf": {
        "subject": "Data Structures",
        "unit": "Unit 3",
        "topic": "Recursion",
        "difficulty": "medium"
    },
    "unit1_intro.pdf": {
        "subject": "Data Structures",
        "unit": "Unit 1",
        "topic": "Introduction",
        "difficulty": "easy"
    }
}
"""

import json
import re
import uuid
from pathlib import Path
from typing import List, Dict


DEFAULT_METADATA = {
    "subject": "unknown",
    "unit": "unknown",
    "topic": "unknown",
    "difficulty": "medium",
}

# Matches a line on its own that separates topic sections within one file,
# e.g. "---" or "===" between "Unit 1: Arrays" and "Unit 1: Time Complexity".
_SECTION_DELIMITER_RE = re.compile(r"^[-=]{3,}\s*$", re.MULTILINE)

# Matches a section header like "Data Structures - Unit 1: Arrays" and
# captures subject / unit / topic from it automatically.
_SECTION_HEADER_RE = re.compile(
    r"^(?P<subject>.+?)\s*-\s*Unit\s*(?P<unit>[\w.]+)\s*:\s*(?P<topic>.+)$"
)


def split_into_topic_sections(text: str) -> List[Dict]:
    """
    Splits a block of text into topic-level sections using '---'/'==='
    delimiters, and auto-detects subject/unit/topic from a header line
    like "Data Structures - Unit 1: Arrays" when present.

    This matters because a single file often covers many topics (e.g. a
    whole unit's worth of notes in one .txt/.pdf). Without this, every
    chunk in that file gets the SAME topic tag from the file-level
    manifest entry, which silently breaks gap-aware retrieval — a chunk
    about Stacks would get tagged "Recursion" just because it happened
    to sit in the same file.

    Falls back to treating the whole text as a single section with no
    auto-detected metadata when no delimiters/headers are found, so
    plain files (or PDFs that don't follow this convention) behave
    exactly as before — auto-detection is additive, not required.
    """
    raw_parts = _SECTION_DELIMITER_RE.split(text)
    sections = []
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        first_line = part.splitlines()[0].strip()
        match = _SECTION_HEADER_RE.match(first_line)
        auto_meta = {}
        if match:
            auto_meta = {
                "subject": match.group("subject").strip(),
                "unit": f"Unit {match.group('unit').strip()}",
                "topic": match.group("topic").strip(),
            }
        sections.append({"text": part, "auto_meta": auto_meta})
    return sections if sections else [{"text": text, "auto_meta": {}}]


def load_manifest(manifest_path: Path) -> Dict[str, Dict]:
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        print(
            f"[chunker] No manifest found at {manifest_path}. "
            "All chunks will use default metadata — you should add a "
            "manifest.json for real use so gap analysis can filter by topic."
        )
        return {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_metadata_for_file(filename: str, manifest: Dict[str, Dict]) -> Dict:
    if filename in manifest:
        merged = DEFAULT_METADATA.copy()
        merged.update(manifest[filename])
        return merged
    return DEFAULT_METADATA.copy()


def chunk_words(text: str, chunk_size: int = 220, overlap: int = 40) -> List[str]:
    """
    Word-based sliding-window chunking. Word-based (not char-based) keeps
    chunks roughly semantically complete and is simple enough to defend
    in a viva. overlap keeps context from being cut off mid-idea at
    chunk boundaries.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(chunk_size - overlap, 1)
    for start in range(0, len(words), step):
        piece = words[start : start + chunk_size]
        if not piece:
            break
        chunks.append(" ".join(piece))
        if start + chunk_size >= len(words):
            break
    return chunks


def build_chunks(
    page_records: List[Dict],
    manifest: Dict[str, Dict],
    chunk_size: int = 220,
    overlap: int = 40,
) -> List[Dict]:
    """
    Takes page-level records from document_loader and produces final
    chunk records ready for embedding:

    {
        "chunk_id": "uuid",
        "text": "...",
        "source_file": "unit3_recursion.pdf",
        "page": 4,
        "subject": "Data Structures",
        "unit": "Unit 3",
        "topic": "Recursion",
        "difficulty": "medium"
    }
    """
    all_chunks = []
    for record in page_records:
        file_meta = get_metadata_for_file(record["source_file"], manifest)
        sections = split_into_topic_sections(record["text"])

        for section in sections:
            # Precedence: DEFAULT < file-level manifest < auto-detected
            # section header. The manifest still supplies things
            # auto-detection can't infer (like difficulty), while a
            # detected header gives finer-grained subject/unit/topic
            # than one manifest entry per file ever could.
            meta = {**file_meta, **section["auto_meta"]}
            pieces = chunk_words(section["text"], chunk_size=chunk_size, overlap=overlap)
            for piece in pieces:
                all_chunks.append(
                    {
                        "chunk_id": str(uuid.uuid4()),
                        "text": piece,
                        "source_file": record["source_file"],
                        "page": record["page"],
                        **meta,
                    }
                )
    return all_chunks


def save_chunks(chunks: List[Dict], output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    print(f"[chunker] Saved {len(chunks)} chunks to {output_path}")
