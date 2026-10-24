from __future__ import annotations
from typing import Any
from .question_bank import get_questions_for_mode

def build_exam_set(subject: str, level: str, topic: str, limit: int = 5) -> list[dict[str, Any]]:
    questions = get_questions_for_mode(subject, level, topic, "exam")
    return questions[:limit]
