from __future__ import annotations
from pathlib import Path
from typing import Any
from datetime import datetime
import re

from .config import STUDENTS_DIR, TOPIC_MASTERY_THRESHOLD
from .storage import ensure_dir, read_json, write_json

def student_dir(student_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", str(student_id or "")):
        raise ValueError("Invalid student ID.")
    return STUDENTS_DIR / student_id

def profile_path(student_id: str) -> Path:
    return student_dir(student_id) / "profile.json"

def progress_path(student_id: str) -> Path:
    return student_dir(student_id) / "progress.json"

def learning_history_path(student_id: str) -> Path:
    return student_dir(student_id) / "learning_history.json"

def exam_history_path(student_id: str) -> Path:
    return student_dir(student_id) / "exam_history.json"

def current_session_path(student_id: str) -> Path:
    return student_dir(student_id) / "current_session.json"

def ensure_student(student_id: str, student_name: str = "Demo Student") -> None:
    ensure_dir(student_dir(student_id))
    if not profile_path(student_id).exists():
        write_json(profile_path(student_id), {
            "student_id": student_id,
            "name": student_name,
            "preferred_language": "English",
        })
    if not progress_path(student_id).exists():
        write_json(progress_path(student_id), {"student_id": student_id, "subjects": {}})
    if not learning_history_path(student_id).exists():
        write_json(learning_history_path(student_id), [])
    if not exam_history_path(student_id).exists():
        write_json(exam_history_path(student_id), [])
    if not current_session_path(student_id).exists():
        write_json(current_session_path(student_id), {})

def get_profile(student_id: str) -> dict[str, Any]:
    ensure_student(student_id)
    return read_json(profile_path(student_id), {})

def get_progress(student_id: str) -> dict[str, Any]:
    ensure_student(student_id)
    return read_json(progress_path(student_id), {"student_id": student_id, "subjects": {}})

def save_progress(student_id: str, progress: dict[str, Any]) -> None:
    write_json(progress_path(student_id), progress)

def get_current_session(student_id: str) -> dict[str, Any]:
    ensure_student(student_id)
    return read_json(current_session_path(student_id), {})

def save_current_session(student_id: str, session: dict[str, Any]) -> None:
    write_json(current_session_path(student_id), session)

def append_learning_history(student_id: str, record: dict[str, Any]) -> None:
    items = read_json(learning_history_path(student_id), [])
    items.append(record)
    write_json(learning_history_path(student_id), items)

def append_exam_history(student_id: str, record: dict[str, Any]) -> None:
    items = read_json(exam_history_path(student_id), [])
    items.append(record)
    write_json(exam_history_path(student_id), items)

def _topic_ref(progress: dict[str, Any], subject: str, level: str, topic: str) -> dict[str, Any]:
    subjects = progress.setdefault("subjects", {})
    subject_ref = subjects.setdefault(subject, {})
    level_ref = subject_ref.setdefault(level, {})
    return level_ref.setdefault(topic, {
        "topic_mastery": 0,
        "status": "new",
        "concept_scores": {},
        "weak_concepts": [],
        "questions_attempted": 0,
        "clarification_requests": 0,
        "ready_for_exam": False,
    })

def update_topic_progress(
    student_id: str,
    subject: str,
    level: str,
    topic: str,
    concept: str,
    score_delta: int,
    weak: bool = False,
    clarification_increment: int = 0,
) -> dict[str, Any]:
    progress = get_progress(student_id)
    topic_ref = _topic_ref(progress, subject, level, topic)

    current = int(topic_ref["concept_scores"].get(concept, 0))
    current = max(0, min(100, current + score_delta))
    topic_ref["concept_scores"][concept] = current

    if weak and concept not in topic_ref["weak_concepts"]:
        topic_ref["weak_concepts"].append(concept)
    if not weak and concept in topic_ref["weak_concepts"] and current >= 70:
        topic_ref["weak_concepts"].remove(concept)

    topic_ref["questions_attempted"] = int(topic_ref.get("questions_attempted", 0)) + 1
    topic_ref["clarification_requests"] = int(topic_ref.get("clarification_requests", 0)) + clarification_increment

    scores = list(topic_ref["concept_scores"].values()) or [0]
    topic_mastery = round(sum(scores) / len(scores))
    topic_ref["topic_mastery"] = topic_mastery
    topic_ref["status"] = "mastered" if topic_mastery >= TOPIC_MASTERY_THRESHOLD else "improving"
    topic_ref["ready_for_exam"] = topic_mastery >= 60

    save_progress(student_id, progress)
    return topic_ref

def increment_clarification(student_id: str, subject: str, level: str, topic: str) -> dict[str, Any]:
    progress = get_progress(student_id)
    topic_ref = _topic_ref(progress, subject, level, topic)
    topic_ref["clarification_requests"] = int(topic_ref.get("clarification_requests", 0)) + 1
    save_progress(student_id, progress)
    return topic_ref

def snapshot_student(student_id: str) -> dict[str, Any]:
    return {
        "profile": get_profile(student_id),
        "progress": get_progress(student_id),
        "session": get_current_session(student_id),
        "learning_history": read_json(learning_history_path(student_id), []),
        "exam_history": read_json(exam_history_path(student_id), []),
    }

def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"
