from __future__ import annotations
from typing import Any

def score_analysis(analysis: dict[str, Any]) -> int:
    level = analysis.get("understanding_level", "weak")
    mapping = {
        "strong": 15,
        "partial": 5,
        "weak": 2,
        "wrong": 0,
        "unclear": 0,
    }
    return int(analysis.get("score_delta", mapping.get(level, 0)))
