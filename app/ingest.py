from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib
import re

from .config import KNOWLEDGEBASE_DIR, INDEX_DIR
from .content_loader import iter_supported_files, extract_text
from .storage import write_json

def split_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks

def infer_chunk_type(path: Path) -> str:
    folder_name = path.parent.name.lower()
    if "question" in folder_name:
        return "question_bank"
    if "answer" in folder_name or "mark" in folder_name:
        return "marking"
    if "example" in folder_name:
        return "example"
    if "note" in folder_name:
        return "note"
    return "general"

def build_topic_index(subject: str, level: str, topic: str) -> dict[str, Any]:
    topic_dir = KNOWLEDGEBASE_DIR / subject / level / topic
    if not topic_dir.exists():
        raise FileNotFoundError(f"Topic directory not found: {topic_dir}")

    docs: list[dict[str, Any]] = []
    for file_path in iter_supported_files(topic_dir):
        raw = extract_text(file_path)
        for idx, chunk in enumerate(split_text(raw)):
            chunk_id = hashlib.md5(f"{file_path}:{idx}:{chunk[:50]}".encode("utf-8")).hexdigest()
            docs.append({
                "chunk_id": chunk_id,
                "subject": subject,
                "level": level,
                "topic": topic,
                "source_file": str(file_path.relative_to(KNOWLEDGEBASE_DIR)),
                "source_name": file_path.name,
                "chunk_index": idx,
                "chunk_type": infer_chunk_type(file_path),
                "text": chunk,
            })

    index = {
        "subject": subject,
        "level": level,
        "topic": topic,
        "document_count": len(docs),
        "chunks": docs,
    }
    out = INDEX_DIR / f"{subject}__{level}__{topic}.json"
    write_json(out, index)
    return index

def rebuild_all_indexes() -> dict[str, Any]:
    built: list[dict[str, str]] = []
    if not KNOWLEDGEBASE_DIR.exists():
        return {"built": built}
    for subject_dir in KNOWLEDGEBASE_DIR.iterdir():
        if not subject_dir.is_dir():
            continue
        for level_dir in subject_dir.iterdir():
            if not level_dir.is_dir():
                continue
            for topic_dir in level_dir.iterdir():
                if not topic_dir.is_dir():
                    continue
                build_topic_index(subject_dir.name, level_dir.name, topic_dir.name)
                built.append({
                    "subject": subject_dir.name,
                    "level": level_dir.name,
                    "topic": topic_dir.name,
                })
    return {"built": built}
