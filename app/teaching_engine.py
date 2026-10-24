from __future__ import annotations
from typing import Any
import re
from .config import KNOWLEDGEBASE_DIR
from .retriever import retrieve_context_text
from .question_bank import get_questions_for_mode, find_question_by_id
from .ai_provider import get_provider
from . import ai_orchestrator
from .student_tracker import snapshot_student
from .tamil_naturalizer import _preferred_followup_translation
from .tamil_fallbacks import known_tamil_translation

provider = get_provider()


def _topic_key_terms_context(subject: str, level: str, topic: str) -> str:
    topic_dir = KNOWLEDGEBASE_DIR / subject / level / topic
    if not topic_dir.exists():
        return ""
    chunks: list[str] = []
    for path in topic_dir.rglob("key_terms.txt"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            continue
        if text:
            chunks.append(f"[Key terms: {path.relative_to(KNOWLEDGEBASE_DIR)}]\n{text}")
    return "\n\n".join(chunks)[:2500]


def _retrieval_with_key_terms(subject: str, level: str, topic: str, query: str) -> str:
    retrieved = retrieve_context_text(subject, level, topic, query)
    key_terms = _topic_key_terms_context(subject, level, topic)
    return "\n\n".join(part for part in (key_terms, retrieved) if part)


def _has_tamil(text: str) -> bool:
    return any("\u0b80" <= ch <= "\u0bff" for ch in (text or ""))


def _question_type_matches(english_question: str, tamil_question: str) -> bool:
    english = re.sub(r"\s+", " ", (english_question or "").strip().lower())
    tamil = re.sub(r"\s+", " ", tamil_question or "").strip()
    if not english or not tamil:
        return False
    if english.startswith("why"):
        return any(token in tamil for token in ("ஏன்", "எதற்காக", "காரணம்"))
    if english.startswith("how"):
        return any(token in tamil for token in ("எப்படி", "எவ்வாறு"))
    if english.startswith("which"):
        return any(token in tamil for token in ("எது", "எந்த"))
    if english.startswith("what"):
        return any(token in tamil for token in ("என்ன", "என்றால்"))
    return True


def _clean_translated_question(english_question: str, tamil_question: str) -> str:
    english = re.sub(r"\s+", " ", (english_question or "").strip().lower())
    tamil = re.sub(r"\s+", " ", (tamil_question or "").strip()).strip('"')

    if english.startswith(("what is ", "what are ", "define ")):
        if "என்றால் என்ன" not in tamil:
            tamil = re.sub(r"^(.+?)\s+என்ன\?$", r"\1 என்றால் என்ன?", tamil)
            tamil = re.sub(r"^(.+?)\s+என்ன$", r"\1 என்றால் என்ன?", tamil)

    if english.startswith("why"):
        tamil = tamil.replace("எங்கள் உணவை பாதுகாப்பதற்கான ஏன்?", "நாம் உணவை ஏன் பாதுகாக்கிறோம்?")
        tamil = tamil.replace("நாம் உணவை பாதுகாப்பதற்கான ஏன்?", "நாம் உணவை ஏன் பாதுகாக்கிறோம்?")
        tamil = tamil.replace("பாதுகாப்பதற்கான ஏன்?", "ஏன் பாதுகாக்கிறோம்?")
        tamil = tamil.replace("நாம் உணவை பாதுகாக்க காரணம் ஏன்?", "நாம் உணவை ஏன் பாதுகாக்கிறோம்?")
        tamil = tamil.replace("காரணம் ஏன்?", "ஏன்?")
        tamil = tamil.replace("காரணம் என்ன?", "ஏன்?")
        tamil = tamil.replace("காரணம் யாது?", "ஏன்?")

    tamil = tamil.replace("அழுத்தவும்", "அழுத்துங்கள்")
    return tamil


def _simple_tamil_question_fallback(english_question: str) -> str:
    english = re.sub(r"\s+", " ", (english_question or "").strip().lower()).rstrip("?")
    known_translation = known_tamil_translation(english_question)
    if known_translation:
        return known_translation
    preferred = _preferred_followup_translation(english_question)
    if preferred:
        return preferred
    if english == "why do we preserve food":
        return "நாம் உணவை ஏன் பாதுகாக்கிறோம்?"
    if english.startswith("what is "):
        term = english_question.strip()[8:].strip(" ?")
        if term:
            return f"{term} என்றால் என்ன?"
    if english.startswith("what are "):
        term = english_question.strip()[9:].strip(" ?")
        if term:
            return f"{term} என்றால் என்ன?"
    return "மேலுள்ள கேள்விக்கு சுருக்கமாக பதில் சொல்ல முடியுமா?"


async def translate_question_to_tamil(subject: str, level: str, topic: str, english_question: str) -> str:
    question = (english_question or "").strip()
    if not question:
        return _simple_tamil_question_fallback(question)
    if _has_tamil(question):
        return question
    preferred = _preferred_followup_translation(question)
    if preferred:
        return preferred
    context = _topic_key_terms_context(subject, level, topic)
    system = (
        "You translate one classroom question into natural Tamil for a primary-school science tutor. "
        "Keep the same meaning, examples, choices, and question type. "
        "Use glossary terms from the supplied context when available. "
        "Return only the Tamil question, no JSON and no explanation."
    )
    user = f"""
English question:
{question}

Glossary/context:
{context[:1200]}
"""
    try:
        translated = (await provider.chat(system, user)).strip()
    except Exception:
        return _simple_tamil_question_fallback(question)
    translated = _clean_translated_question(question, translated.splitlines()[0])
    if not _has_tamil(translated) or not _question_type_matches(question, translated):
        strict_system = (
            "Translate one English classroom question into natural Tamil. "
            "Preserve the question type exactly. "
            "If English starts with why, Tamil must include ஏன், எதற்காக, or காரணம். "
            "If English starts with what, Tamil must include என்ன or என்றால். "
            "If English starts with how, Tamil must include எப்படி or எவ்வாறு. "
            "If English starts with which, Tamil must include எது or எந்த. "
            "Do not answer the question. Return only the Tamil question."
        )
        retry_user = f"""
The Tamil translation below is missing Tamil text or changed the question type.
Rewrite it again as one natural Tamil classroom question.
Keep the same meaning, examples, choices, and question type.
Return only the Tamil question.

English question:
{question}

Bad Tamil:
{translated}

Glossary/context:
{context[:1200]}
"""
        try:
            translated = _clean_translated_question(
                question,
                (await provider.chat(strict_system, retry_user)).strip().splitlines()[0],
            )
        except Exception:
            return _simple_tamil_question_fallback(question)
    translated = _clean_translated_question(question, translated)
    if not _has_tamil(translated) or not _question_type_matches(question, translated):
        return _simple_tamil_question_fallback(question)
    return translated if translated.endswith("?") else f"{translated.rstrip('.!?')}?"


def _question_terms(text: str) -> set[str]:
    stop_words = {
        "the",
        "and",
        "are",
        "all",
        "for",
        "with",
        "that",
        "this",
        "what",
        "why",
        "how",
        "true",
        "false",
        "explain",
    }
    return {
        word
        for word in re.findall(r"[a-zA-Z]+", (text or "").lower())
        if len(word) > 2 and word not in stop_words
    }


def _is_near_duplicate_question(first: dict[str, Any], second: dict[str, Any]) -> bool:
    first_terms = _question_terms(str(first.get("question_text") or ""))
    second_terms = _question_terms(str(second.get("question_text") or ""))
    if not first_terms or not second_terms:
        return False
    from difflib import SequenceMatcher
    return SequenceMatcher(None, str(first.get("question_text", "")).lower(), str(second.get("question_text", "")).lower()).ratio() >= 0.92

def choose_first_question(subject: str, level: str, topic: str, mode: str) -> dict[str, Any] | None:
    questions = get_questions_for_mode(subject, level, topic, mode)
    if not questions:
        return None
    # Prefer easy first in learning
    if mode == "learning":
        questions = sorted(questions, key=lambda q: {"easy": 0, "medium": 1, "hard": 2}.get(q.get("difficulty","medium"), 1))
    return questions[0]

def choose_next_question(
    subject: str,
    level: str,
    topic: str,
    mode: str,
    asked_question_ids: list[str],
    current_question: dict[str, Any] | None,
    analysis: dict[str, Any] | None,
) -> dict[str, Any] | None:
    questions = get_questions_for_mode(subject, level, topic, mode)
    remaining = [q for q in questions if q.get("question_id") not in set(asked_question_ids)]

    if not remaining:
        return None

    if current_question and analysis:
        action = (
            analysis.get("recommended_next_action")
            or analysis.get("recommended_action")
            or ""
        )
        if action in {"move_next", "start_activity"}:
            non_repeating = [q for q in remaining if not _is_near_duplicate_question(current_question, q)]
            if non_repeating:
                return non_repeating[0]

        follow_id = current_question.get("followup_question_id")
        if action in {"reteach", "ask_followup", "clarify", "reteach_then_followup"} and follow_id:
            q = find_question_by_id(subject, level, topic, follow_id)
            if q and q.get("question_id") not in set(asked_question_ids):
                return q

        concept = analysis.get("concept") or current_question.get("concept")
        concept_match = [q for q in remaining if q.get("concept") == concept]
        if concept_match:
            concept_match = sorted(concept_match, key=lambda q: {"easy": 0, "medium": 1, "hard": 2}.get(q.get("difficulty","medium"), 1))
            return concept_match[0]

    return remaining[0]

def _session_learning_history(items: list[dict[str, Any]], session: dict[str, Any]) -> list[dict[str, Any]]:
    started_at = str(session.get("started_at") or "")
    asked_ids = set(session.get("asked_question_ids") or [])
    subject = session.get("subject")
    level = session.get("level")
    topic = session.get("topic")

    current_items: list[dict[str, Any]] = []
    for item in items or []:
        if subject and item.get("subject") != subject:
            continue
        if level and item.get("level") != level:
            continue
        if topic and item.get("topic") != topic:
            continue
        if started_at:
            same_session = item.get("session_started_at") == started_at
            after_start = str(item.get("timestamp") or "") >= started_at
            if not (same_session or after_start):
                continue
        if asked_ids and item.get("question_id") not in asked_ids:
            continue
        current_items.append(item)
    return current_items[-5:]


def _student_context(student_id: str, session: dict[str, Any] = None) -> dict[str, Any]:
    snap = snapshot_student(student_id)
    learning_history = snap.get("learning_history", []) or []
    if session:
        learning_history = _session_learning_history(learning_history, session)
    else:
        learning_history = learning_history[-5:]
    return {
        "profile": snap.get("profile", {}),
        "progress": snap.get("progress", {}),
        "recent_learning_history": learning_history,
        "recent_exam_history": (snap.get("exam_history", []) or [])[-5:],
    }


async def tutor_learning_turn(
    *,
    student_id: str,
    subject: str,
    level: str,
    topic: str,
    session: dict[str, Any],
    question: dict[str, Any],
    student_message: str,
) -> dict[str, Any]:
    context = _retrieval_with_key_terms(subject, level, topic, question.get("question_text", ""))
    student_ctx = _student_context(student_id, session)
    return await ai_orchestrator.tutor_turn(
        provider,
        topic=topic,
        session=session,
        question=question,
        student_message=student_message,
        retrieved_context=context,
        student_profile=student_ctx["profile"],
        progress=student_ctx["progress"],
        recent_learning_history=student_ctx["recent_learning_history"],
    )


async def score_exam_turn(
    *,
    student_id: str,
    subject: str,
    level: str,
    topic: str,
    question: dict[str, Any],
    student_answer: str,
) -> dict[str, Any]:
    context = _retrieval_with_key_terms(subject, level, topic, question.get("question_text", ""))
    student_ctx = _student_context(student_id)
    return await ai_orchestrator.score_exam_answer(
        provider,
        topic=topic,
        question=question,
        student_answer=student_answer,
        retrieved_context=context,
        student_profile=student_ctx["profile"],
        progress=student_ctx["progress"],
        recent_exam_history=student_ctx["recent_exam_history"],
    )

async def clarify_with_context(subject: str, level: str, topic: str, ask: str) -> str:
    context = _retrieval_with_key_terms(subject, level, topic, ask)
    return await ai_orchestrator.clarify(provider, ask=ask, retrieved_context=context, topic=topic)
