from __future__ import annotations
from typing import Any
from .student_tracker import ensure_student, save_current_session, get_current_session, now_iso

def start_session(
    student_id: str,
    student_name: str,
    subject: str,
    level: str,
    topic: str,
    mode: str,
) -> dict[str, Any]:
    ensure_student(student_id, student_name)
    session = {
        "student_id": student_id,
        "mode": mode,
        "subject": subject,
        "level": level,
        "topic": topic,
        "current_question_id": None,
        "asked_question_ids": [],
        "current_concept": None,
        "exam_answers": [],
        "last_analysis": None,
        "clarification_open": False,
        "topic_status": "in_progress",
        "started_at": now_iso(),
    }
    save_current_session(student_id, session)
    return session

def update_session(student_id: str, **kwargs: Any) -> dict[str, Any]:
    session = get_current_session(student_id)
    session.update(kwargs)
    save_current_session(student_id, session)
    return session
