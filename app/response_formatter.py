from __future__ import annotations
from typing import Any
import re

from .tamil_fallbacks import known_tamil_translation


FORBIDDEN_VISIBLE_PHRASES = {
    "One important idea is still missing.",
    "This idea is about tiny living things.",
    "Which part do you want to work on first?",
    "Can you add that missing part?",
}


def _bilingual_message(
    english_explanation: str,
    tamil_explanation: str,
    english_question: str,
    tamil_question: str,
) -> str:
    return (
        f"{english_explanation.strip()}\n\n"
        f"{english_question.strip()}\n\n"
        f"{tamil_explanation.strip()}\n\n"
        f"{tamil_question.strip()}"
    )


def _student_visible_reply_from_fields(data: dict[str, Any]) -> str:
    english_response = str(data.get("english_response") or "").strip()
    english_followup = str(data.get("english_followup") or "").strip()
    tamil_response = str(data.get("tamil_response") or "").strip()
    tamil_followup = str(data.get("tamil_followup") or "").strip()
    if not any([english_response, english_followup, tamil_response, tamil_followup]):
        return ""
    return _bilingual_message(
        english_response,
        tamil_response,
        english_followup,
        tamil_followup,
    )


def _split_bilingual_message(text: str) -> tuple[str, str, str, str] | None:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if len(lines) < 4:
        return None
    return lines[0], lines[1], lines[2], lines[3]


def _looks_like_tamil(text: str) -> bool:
    return any("\u0b80" <= ch <= "\u0bff" for ch in (text or ""))


def _strip_markdown_noise(text: str) -> str:
    cleaned = re.sub(r"[`*_#>-]+", " ", text or "")
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _trim_to_two_sentences(text: str) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", _strip_markdown_noise(text)) if p.strip()]
    return " ".join(parts[:2]).strip()


def _filler_free(text: str) -> str:
    cleaned = text or ""
    banned_phrases = [
        "Let's make this clearer",
        "You're getting close",
        "Good try",
        "Let's think again",
        "Let's make the idea a little clearer",
        "You're on the right track",
        "Nice work",
        "Nice thinking",
        "நல்ல முயற்சி",
        "இதைக் மிகவும் எளிதாக பார்க்கலாம்",
        "இதைக் கொஞ்சம் தெளிவாகப் பார்ப்போம்",
        "நீங்கள் சரியான பாதையில் இருக்கிறீர்கள்",
    ]
    for phrase in banned_phrases:
        cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned


def _contains_forbidden_phrase(text: str) -> bool:
    lowered = (text or "").lower()
    return any(phrase.lower() in lowered for phrase in FORBIDDEN_VISIBLE_PHRASES)


def _fallback_tamil_response(english_response: str) -> str:
    translated = known_tamil_translation(english_response)
    if translated:
        return translated
    return "இந்தக் கருத்தை இன்னும் எளிமையாகப் பார்ப்போம்."


def _fallback_tamil_question(english_question: str) -> str:
    translated = known_tamil_translation(english_question)
    if translated:
        return translated
    return "இந்தக் கேள்விக்கு ஒரு சுருக்கமான பதில் சொல்ல முடியுமா?"


def _clean_tamil_quality(text: str) -> str:
    cleaned = text or ""
    replacements = {
        "புலன் கண்களால்": "கண்களால்",
        "பகுதியாக உரியது": "ஒரு பகுதி சரியாக உள்ளது",
        "எண்ணுங்களா": "சொல்ல முடியுமா",
        "சொல்லுங்களா": "சொல்ல முடியுமா",
        "பெயரிடுங்கள்": "பெயரை சொல்ல முடியுமா",
        "உங்கள் கருத்தில் எடுத்துக்கொள்ளுங்களா": "பெயரை சொல்ல முடியுமா",
        "உங்கள் கொள்கையில் சேர்க்கலாமா": "பெயரை சொல்ல முடியுமா",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return cleaned


def _extract_question_text(text: str, fallback_question: str) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", _strip_markdown_noise(text)) if p.strip()]
    for part in parts:
        if "?" in part:
            return part if part.endswith("?") else part.rstrip(".!") + "?"
    fallback = _strip_markdown_noise(fallback_question).rstrip(".!?")
    return f"{fallback}?"


def _extract_response_text(text: str, fallback_response: str) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", _strip_markdown_noise(text)) if p.strip()]
    parts = [p for p in parts if not p.lower().startswith("[source:") and not p.lower().startswith("[sheet]")]
    non_questions = [p for p in parts if "?" not in p]
    candidate = " ".join(non_questions[:2]).strip()
    candidate = _filler_free(candidate)
    if candidate:
        if not re.search(r"[.!?]$", candidate):
            candidate = f"{candidate}."
        return _trim_to_two_sentences(candidate)
    fallback = _trim_to_two_sentences(_filler_free(fallback_response))
    if fallback:
        if not re.search(r"[.!?]$", fallback):
            fallback = f"{fallback}."
        return fallback
    return "This idea is important."


def validate_and_format_response(
    reply: str,
    *,
    fallback_response: str,
    fallback_question: str,
) -> str:
    parts = _split_bilingual_message(reply)
    english_response = ""
    english_question = ""
    tamil_response = ""
    tamil_question = ""

    if parts:
        english_response, english_question, tamil_response, tamil_question = parts
    else:
        lines = [line.strip() for line in (reply or "").splitlines() if line.strip()]
        english_lines = [line for line in lines if not _looks_like_tamil(line)]
        tamil_lines = [line for line in lines if _looks_like_tamil(line)]
        if english_lines:
            english_response = english_lines[0]
            english_question = english_lines[1] if len(english_lines) > 1 else ""
        if tamil_lines:
            tamil_response = tamil_lines[0]
            tamil_question = tamil_lines[1] if len(tamil_lines) > 1 else ""

    english_response = _extract_response_text(english_response or reply, fallback_response)
    english_question = _extract_question_text(english_question or reply, fallback_question)
    if _contains_forbidden_phrase(english_response):
        english_response = _extract_response_text("", fallback_response)
    if _contains_forbidden_phrase(english_question):
        english_question = _extract_question_text("", fallback_question)
    tamil_response = _extract_response_text(
        tamil_response,
        _fallback_tamil_response(english_response),
    )
    tamil_question = _extract_question_text(
        tamil_question,
        _fallback_tamil_question(english_question),
    )

    if not _looks_like_tamil(tamil_response):
        tamil_response = _fallback_tamil_response(english_response)
    if not _looks_like_tamil(tamil_question):
        tamil_question = _fallback_tamil_question(english_question)
    tamil_response = _clean_tamil_quality(tamil_response)
    tamil_question = _clean_tamil_quality(tamil_question)
    if _contains_forbidden_phrase(tamil_response):
        tamil_response = _fallback_tamil_response(english_response)
    if _contains_forbidden_phrase(tamil_question):
        tamil_question = _fallback_tamil_question(english_question)

    return _bilingual_message(
        english_response,
        tamil_response,
        english_question,
        tamil_question,
    )


def _extract_first_question_line(text: str, fallback_question: str) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[?!])\s+|(?<=\.)\s+", (text or "").strip()) if p.strip()]
    for part in parts:
        if "?" in part:
            return part if part.endswith("?") else part.rstrip(".!") + "?"
    return fallback_question


def _ensure_bilingual_reply(reply: str, fallback_question: str) -> str:
    parts = _split_bilingual_message(reply)
    if parts:
        english_explanation, english_question, tamil_explanation, tamil_question = parts
        english_question = _extract_first_question_line(english_question, fallback_question)
        tamil_question = _extract_first_question_line(tamil_question, "மேலுள்ள கேள்விக்கு சுருக்கமாக பதில் சொல்ல முடியுமா?")
        return _bilingual_message(
            english_explanation,
            tamil_explanation,
            english_question,
            tamil_question,
        )

    lines = [line.strip() for line in (reply or "").splitlines() if line.strip()]
    english_lines = [line for line in lines if not _looks_like_tamil(line)]
    tamil_lines = [line for line in lines if _looks_like_tamil(line)]
    english_explanation = english_lines[0] if english_lines else "Let's make this a little clearer."
    tamil_explanation = tamil_lines[0] if tamil_lines else "இதைக் கொஞ்சம் தெளிவாகப் பார்ப்போம்."
    english_question = _extract_first_question_line(
        english_lines[-1] if english_lines else "",
        fallback_question,
    )
    tamil_question = _extract_first_question_line(
        tamil_lines[-1] if tamil_lines else "",
        "மேலுள்ள கேள்விக்கு சுருக்கமாக பதில் சொல்ல முடியுமா?",
    )
    return _bilingual_message(
        english_explanation,
        tamil_explanation,
        english_question,
        tamil_question,
    )


def _question_count(text: str) -> int:
    parts = _split_bilingual_message(text)
    if parts:
        english_question = parts[1]
        return 1 if "?" in english_question else 0
    return (text or "").count("?")


def _ensure_single_question(reply: str, fallback_question: str) -> str:
    bilingual = _split_bilingual_message(reply)
    if bilingual:
        return _ensure_bilingual_reply(reply, fallback_question)

    text = re.sub(r"\s+", " ", (reply or "").strip())
    if not text:
        return fallback_question
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
    non_questions = [p for p in parts if "?" not in p]
    questions = [p for p in parts if "?" in p]
    if not questions:
        base = " ".join(non_questions[:2]).strip()
        return f"{base} {fallback_question}".strip()
    question = questions[-1]
    if not question.endswith("?"):
        question = question.rstrip(".!") + "?"
    base = " ".join(non_questions[:2]).strip()
    combined = f"{base} {question}".strip() if base else question
    return combined
