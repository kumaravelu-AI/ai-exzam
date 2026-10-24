from __future__ import annotations
from pathlib import Path
from typing import Any
import re

from .config import INDEX_DIR, MAX_RETRIEVED_CHUNKS
from .storage import read_json

def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())

def score_chunk(query: str, chunk: dict[str, Any]) -> float:
    q_tokens = tokenize(query)
    c_text = chunk.get("text", "").lower()
    score = 0.0
    for token in q_tokens:
        if token in c_text:
            score += 1.0
    chunk_type = chunk.get("chunk_type", "")
    if "question" in chunk_type:
        score += 0.2
    if "example" in chunk_type:
        score += 0.2
    return score

def load_topic_index(subject: str, level: str, topic: str) -> dict[str, Any]:
    path = INDEX_DIR / f"{subject}__{level}__{topic}.json"
    return read_json(path, {"subject": subject, "level": level, "topic": topic, "chunks": []})

def retrieve_chunks(subject: str, level: str, topic: str, query: str, limit: int = MAX_RETRIEVED_CHUNKS) -> list[dict[str, Any]]:
    index = load_topic_index(subject, level, topic)
    chunks = index.get("chunks", [])
    scored = [(score_chunk(query, c), c) for c in chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [c for s, c in scored if s > 0][:limit]
    if not top:
        top = chunks[:limit]
    return top

def retrieve_context_text(subject: str, level: str, topic: str, query: str, limit: int = MAX_RETRIEVED_CHUNKS) -> str:
    top = retrieve_chunks(subject, level, topic, query, limit=limit)
    formatted = []
    for item in top:
        formatted.append(
            f"[SOURCE: {item.get('source_name')} | TYPE: {item.get('chunk_type')}]\n{item.get('text','')}"
        )
    return "\n\n".join(formatted)

def topic_has_index(subject: str, level: str, topic: str) -> bool:
    path = INDEX_DIR / f"{subject}__{level}__{topic}.json"
    return path.exists()
