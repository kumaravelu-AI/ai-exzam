from __future__ import annotations

from typing import Any
from difflib import SequenceMatcher
import re

from .response_formatter import (
    _contains_forbidden_phrase,
    _split_bilingual_message,
    validate_and_format_response,
)


def _strip_json_fence(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _looks_confused(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return any(
        phrase in lowered
        for phrase in (
            "don't understand",
            "dont understand",
            "do not understand",
            "don't know",
            "dont know",
            "do not know",
            "not sure",
            "confused",
            "explain",
            "simplest",
            "easiest",
            "you tell me",
            "tell me",
        )
    )


def _looks_strongly_confused(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return any(
        phrase in lowered
        for phrase in (
            "i don't understand",
            "i dont understand",
            "i do not understand",
            "i don't know",
            "i dont know",
            "i do not know",
            "still confused",
            "you tell me",
            "explain clearly",
            "simplest way",
            "easiest way",
        )
    )


def _recent_followup_questions(recent_learning_history: list[dict[str, Any]]) -> list[str]:
    questions: list[str] = []
    for item in (recent_learning_history or [])[-4:]:
        reply = str(item.get("tutor_reply") or item.get("feedback") or "")
        parts = _split_bilingual_message(reply)
        if parts:
            questions.append(parts[1].strip())
            continue
        match = re.search(r"[^.!?]*\?", reply)
        if match:
            questions.append(match.group(0).strip())
    return [q for q in questions if q]


def _question_from_text(text: str) -> str:
    match = re.search(r"[^.!?]*\?", text or "")
    return match.group(0).strip() if match else ""


def _parse_options_from_text(question_text: str) -> list[str]:
    text = re.sub(r"\s+", " ", question_text or "").strip()
    if ":" in text:
        text = text.split(":", 1)[1]
    text = text.rstrip("?.")
    text = re.sub(r"\bor\b", ",", text, flags=re.IGNORECASE)
    text = re.sub(r"\band\b", ",", text, flags=re.IGNORECASE)
    options = [part.strip(" ,.;") for part in text.split(",") if part.strip(" ,.;")]
    return [option for option in options if 0 < len(option.split()) <= 5][:6]


def _synthesized_options(question: dict[str, Any]) -> list[str]:
    for key in ("options", "choices"):
        value = question.get(key)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()][:6]
        if isinstance(value, str) and value.strip():
            return _parse_options_from_text(value)
    question_type = str(question.get("question_type") or "").strip().lower()
    if question_type != "mcq":
        return []
    return _parse_options_from_text(str(question.get("question_text") or ""))


def _format_options_question(question: dict[str, Any]) -> tuple[str, str]:
    question_text = str(question.get("question_text") or "").strip()
    question_type = str(question.get("question_type") or "").strip().lower()
    if question_type != "mcq":
        return question_text, "மேலுள்ள கேள்விக்கு சுருக்கமாக பதில் சொல்ல முடியுமா?"

    expected = str(question.get("expected_answer") or "").strip().lower()
    if "true or false" in question_text.lower() or expected in {"true", "false"}:
        return question_text, "சரி அல்லது தவறு என்று சொல்ல முடியுமா?"

    options = _synthesized_options(question)
    if options and ":" not in question_text:
        english_options = f"{', '.join(options[:-1])}, or {options[-1]}" if len(options) > 1 else options[0]
        question_text = f"{question_text.rstrip(' ?')}: {english_options}?"
    return question_text, "இந்த தேர்வுகளில் சரியான பதிலை தேர்வு செய்ய முடியுமா?"


def _fallback_from_question(question: dict[str, Any], *, confused: bool = False) -> tuple[str, str]:
    explanation = str(question.get("explanation") or "").strip()
    expected = str(question.get("expected_answer") or "").strip()
    hint = str(question.get("hint") or "").strip()
    question_text = str(question.get("question_text") or "").strip()
    response = explanation or expected or hint or "This question is checking one idea from the lesson."
    if confused:
        response = explanation or hint or expected or "I will explain the idea in a simpler way."
    followup = question_text if question_text.endswith("?") else "Can you answer this in one short sentence?"
    return response, followup


def _word_list(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-zA-Z]+", (text or "").lower()) if len(word) > 3]


def _term_present_in_student(term: str, student_terms: list[str]) -> bool:
    if term in student_terms:
        return True
    return any(SequenceMatcher(None, term, student_term).ratio() >= 0.78 for student_term in student_terms)


def _has_unsupported_student_attribution(reply: str, student_message: str) -> bool:
    attribution_patterns = (
        "you mentioned",
        "you said",
        "you listed",
        "you gave",
        "you provided",
        "you included",
        "you pointed out",
    )
    lower_reply = (reply or "").lower()
    if not any(pattern in lower_reply for pattern in attribution_patterns):
        return False

    student_terms = _word_list(student_message)
    if not student_terms:
        return True

    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", lower_reply) if part.strip()]
    for sentence in sentences:
        if not any(pattern in sentence for pattern in attribution_patterns):
            continue
        attributed_terms = [
            word
            for word in _word_list(sentence)
            if word not in {
                "you",
                "your",
                "mentioned",
                "said",
                "listed",
                "gave",
                "provided",
                "included",
                "pointed",
                "correct",
                "right",
                "answer",
                "method",
                "methods",
                "like",
                "such",
                "other",
                "common",
            }
        ]
        unsupported = [term for term in attributed_terms if not _term_present_in_student(term, student_terms)]
        if len(unsupported) >= 2:
            return True
    return False


def _neutralize_unsupported_student_attribution(reply: str, student_message: str) -> str:
    if not _has_unsupported_student_attribution(reply, student_message):
        return reply
    cleaned = re.sub(
        r"\bYou\s+(mentioned|listed|gave|provided|included|pointed out)\b",
        "The lesson also includes",
        reply,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bYou\s+said\b", "The lesson also says", cleaned, flags=re.IGNORECASE)
    return cleaned


def _reply_quality_issues(reply: str, question: dict[str, Any], student_message: str) -> list[str]:
    issues: list[str] = []
    parts = _split_bilingual_message(reply)
    if not parts:
        issues.append("Response must have exactly four visible sections.")
        return issues

    english_response, english_followup, tamil_response, tamil_followup = parts
    if re.search(r"[\u0B80-\u0BFF]", f"{english_response}\n{english_followup}"):
        issues.append("English sections must not contain Tamil text.")
    if not re.search(r"[\u0B80-\u0BFF]", f"{tamil_response}\n{tamil_followup}"):
        issues.append("Tamil sections must be in Tamil.")
    if _contains_forbidden_phrase(reply):
        issues.append("Response contains a forbidden repeated phrase.")

    english_question = _question_from_text(english_followup)
    if not english_question:
        issues.append("English follow-up must contain one question.")
    if english_followup.count("?") > 1:
        issues.append("English follow-up must contain only one question.")
    if tamil_followup.count("?") > 1:
        issues.append("Tamil follow-up must contain only one question.")

    lower_followup = english_followup.lower()
    if (
        ("which one" in lower_followup or "which of the following" in lower_followup)
        and not any(marker in lower_followup for marker in (":", " or ", ","))
    ):
        issues.append("Choice-style questions must include visible options.")

    lower_reply = reply.lower()
    if any(
        phrase in lower_reply
        for phrase in (
            "captures the basic meaning",
            "provided a correct answer",
            "matches the concept",
            "use the hint to improve",
        )
    ):
        issues.append("Rewrite backend-style evaluation wording as natural teacher feedback.")
    if _has_unsupported_student_attribution(reply, student_message):
        issues.append("Do not attribute examples, methods, or details to the student unless the student actually said them.")
    if _looks_confused(student_message) and any(
        phrase in lower_reply
        for phrase in (
            "what do you think?",
            "can you think of",
            "which part do you want",
            "let's break it down",
        )
    ):
        issues.append("Confused students need a direct explanation before another open question.")
    if _looks_confused(student_message):
        english_response = parts[0].strip().lower()
        has_explanation_signal = any(
            token in english_response
            for token in (" is ", " are ", " means ", " because ", " answer ", " use ", " helps ", " not ")
        )
        if not has_explanation_signal:
            issues.append("Confused students need an answer or explanation in the English response.")

    awkward_tamil = (
        "நீங்கள் யாக இருக்கிறீர்கள்",
        "உங்கள் கருத்தில் எடுத்துக்கொள்ளுங்களா",
        "உங்களுக்கு எண்ணம் வருகிறதா",
        "முந்தைய கேள்விக்கு திரும்புங்கள்",
        "நீங்கள் கூறியதாவது",
        "உங்கள் கவனத்தில் கொள்ளுங்களா",
    )
    if any(phrase in reply for phrase in awkward_tamil):
        issues.append("Tamil should be natural school-level Tamil.")
    return issues


def _apply_tutor_guardrails(
    *,
    result: dict[str, Any],
    question: dict[str, Any],
    student_message: str,
    recent_learning_history: list[dict[str, Any]],
) -> dict[str, Any]:
    guarded = dict(result)
    fallback_response, fallback_question = _fallback_from_question(
        question,
        confused=_looks_confused(student_message) or _looks_strongly_confused(student_message),
    )
    current_reply = str(guarded.get("student_visible_reply") or "")
    if _contains_forbidden_phrase(current_reply):
        current_reply = ""
    current_reply = _neutralize_unsupported_student_attribution(current_reply, student_message)
    guarded["student_visible_reply"] = validate_and_format_response(
        current_reply,
        fallback_response=fallback_response,
        fallback_question=fallback_question,
    )
    return guarded
