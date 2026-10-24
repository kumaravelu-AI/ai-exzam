from __future__ import annotations

from typing import Any
from difflib import SequenceMatcher
import json
import re

from .response_formatter import _extract_first_question_line, _split_bilingual_message


DECISION_INTENTS = {
    "answering_current_question",
    "asking_direct_question",
    "confused",
    "complaint",
    "off_topic",
    "wants_to_move_on",
    "unclear",
}

ANSWER_QUALITIES = {"correct", "partial", "wrong", "unclear"}

NEXT_ACTIONS = {
    "answer_directly",
    "explain_then_check",
    "acknowledge_and_move_next",
    "correct_misconception",
    "ask_easier_question",
    "give_example",
    "change_question",
}


DEFAULT_DECISION = {
    "student_message_intent": "unclear",
    "interpreted_student_meaning": "",
    "active_question_answered": False,
    "answer_quality": "unclear",
    "matched_concepts": [],
    "missing_concepts": [],
    "should_repeat_question": False,
    "should_move_next": False,
    "must_explain_first": False,
    "next_teaching_action": "explain_then_check",
    "reason_summary": "Decision fallback used because the tutor decision could not be parsed.",
}


def _strip_json_fence(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _short_text(text: str, limit: int = 900) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _terms(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-zA-Z]+", (text or "").lower()) if len(word) > 3]


def _term_matches(term: str, student_terms: list[str]) -> bool:
    if term in student_terms:
        return True
    if any(
        (len(term) >= 5 and term.startswith(student_term))
        or (len(student_term) >= 5 and student_term.startswith(term))
        for student_term in student_terms
    ):
        return True
    return any(SequenceMatcher(None, term, student_term).ratio() >= 0.72 for student_term in student_terms)


def _is_definition_question(question: dict[str, Any]) -> bool:
    text = re.sub(r"\s+", " ", str(question.get("question_text") or "").strip().lower())
    return text.startswith(("what is ", "what are ", "define ", "what does ")) or " meaning" in text


def _definition_answer_matches(question: dict[str, Any], student_message: str) -> bool:
    student_terms = _terms(student_message)
    if len(student_terms) < 2:
        return False
    student_text = re.sub(r"\s+", " ", (student_message or "").strip().lower())
    reference = " ".join([
        str(question.get("expected_answer") or ""),
        str(question.get("explanation") or ""),
        " ".join(str(term) for term in (question.get("keywords") or [])),
    ])
    reference_text = reference.lower()
    purpose_pairs = (
        ("prevent", "spoil"),
        ("stop", "spoil"),
        ("slow", "spoil"),
        ("last", "long"),
    )
    if any(all(piece in student_text and piece in reference_text for piece in pair) for pair in purpose_pairs):
        return True
    reference_terms = [
        term
        for term in _terms(reference)
        if term not in {"question", "answer", "example", "examples"}
    ]
    if not reference_terms:
        return False
    matches = [term for term in reference_terms if _term_matches(term, student_terms)]
    return len(set(matches)) >= 2 or (len(set(matches)) >= 1 and len(student_terms) <= 4)


def _enforce_definition_decision(
    decision: dict[str, Any],
    question: dict[str, Any],
    student_message: str,
) -> dict[str, Any]:
    if not _is_definition_question(question):
        return decision
    if decision.get("student_message_intent") != "answering_current_question":
        return decision
    if not _definition_answer_matches(question, student_message):
        return decision
    updated = dict(decision)
    updated["active_question_answered"] = True
    updated["answer_quality"] = "correct"
    updated["missing_concepts"] = []
    updated["should_repeat_question"] = False
    updated["should_move_next"] = True
    updated["next_teaching_action"] = "acknowledge_and_move_next"
    updated["reason_summary"] = "Student gave the main meaning of the definition question."
    return updated


def _safe_list(value: Any, limit: int = 8) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()][:limit]
    if isinstance(value, str) and value.strip():
        return [value.strip()][:limit]
    return []


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _coerce_choice(value: Any, allowed: set[str], fallback: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else fallback


def _question_context(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_id": question.get("question_id"),
        "question_text": question.get("question_text"),
        "question_type": question.get("question_type"),
        "expected_answer": question.get("expected_answer"),
        "keywords": question.get("keywords") or [],
        "concept": question.get("concept"),
        "hint": question.get("hint"),
        "explanation": question.get("explanation"),
        "misconception_tag": question.get("misconception_tag"),
        "followup_question_id": question.get("followup_question_id"),
    }


def _compact_history(items: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in (items or [])[-limit:]:
        compact.append({
            "question_text": item.get("question_text", ""),
            "student_answer": item.get("student_answer", ""),
            "analysis": item.get("analysis", {}),
            "tutor_reply": item.get("tutor_reply") or item.get("feedback", ""),
        })
    return compact


def _latest_bot_question(history: list[dict[str, Any]]) -> str:
    for item in reversed(history or []):
        reply = str(item.get("tutor_reply") or item.get("feedback") or "").strip()
        parts = _split_bilingual_message(reply)
        if parts:
            return parts[1]
        question = _extract_first_question_line(reply, "")
        if question:
            return question
    return ""


async def _chat_json(provider: Any, system: str, user: str) -> dict[str, Any]:
    text = await provider.chat(system, user)
    try:
        return json.loads(_strip_json_fence(text))
    except json.JSONDecodeError:
        repaired = await provider.chat(
            "Repair the text into one valid JSON object only. Do not add markdown.",
            f"Broken JSON:\n{text}",
        )
        return json.loads(_strip_json_fence(repaired))


def _coerce_decision(data: dict[str, Any]) -> dict[str, Any]:
    decision = dict(DEFAULT_DECISION)
    decision.update({
        "student_message_intent": _coerce_choice(
            data.get("student_message_intent"),
            DECISION_INTENTS,
            decision["student_message_intent"],
        ),
        "interpreted_student_meaning": _short_text(str(data.get("interpreted_student_meaning") or ""), 260),
        "active_question_answered": _safe_bool(data.get("active_question_answered")),
        "answer_quality": _coerce_choice(
            data.get("answer_quality"),
            ANSWER_QUALITIES,
            decision["answer_quality"],
        ),
        "matched_concepts": _safe_list(data.get("matched_concepts"), 8),
        "missing_concepts": _safe_list(data.get("missing_concepts"), 8),
        "should_repeat_question": _safe_bool(data.get("should_repeat_question")),
        "should_move_next": _safe_bool(data.get("should_move_next")),
        "must_explain_first": _safe_bool(data.get("must_explain_first")),
        "next_teaching_action": _coerce_choice(
            data.get("next_teaching_action"),
            NEXT_ACTIONS,
            decision["next_teaching_action"],
        ),
        "reason_summary": _short_text(str(data.get("reason_summary") or decision["reason_summary"]), 260),
    })
    if decision["answer_quality"] == "correct" or decision["active_question_answered"]:
        decision["active_question_answered"] = True
    if decision["answer_quality"] != "correct":
        decision["should_move_next"] = False
        if decision["next_teaching_action"] == "acknowledge_and_move_next":
            decision["next_teaching_action"] = "explain_then_check"
    else:
        decision["missing_concepts"] = []
    if decision["should_move_next"]:
        decision["should_repeat_question"] = False
    if decision["answer_quality"] != "correct" and decision["student_message_intent"] in {"confused", "complaint"}:
        decision["should_move_next"] = False
    if (
        decision["student_message_intent"] in {"asking_direct_question", "confused", "complaint"}
        or decision["next_teaching_action"] in {"answer_directly", "explain_then_check", "correct_misconception", "give_example", "ask_easier_question"}
    ):
        decision["must_explain_first"] = True
    return decision


def _fallback_decision(question: dict[str, Any], student_message: str) -> dict[str, Any]:
    text = (student_message or "").strip()
    lowered = text.lower()
    decision = dict(DEFAULT_DECISION)
    decision["interpreted_student_meaning"] = text[:260]
    if "?" in text:
        decision["student_message_intent"] = "asking_direct_question"
        decision["next_teaching_action"] = "answer_directly"
        decision["must_explain_first"] = True
    elif any(phrase in lowered for phrase in ("don't know", "dont know", "not sure", "don't understand", "dont understand")):
        decision["student_message_intent"] = "confused"
        decision["next_teaching_action"] = "explain_then_check"
        decision["must_explain_first"] = True
    elif any(phrase in lowered for phrase in ("next question", "move on", "different question", "boring")):
        decision["student_message_intent"] = "wants_to_move_on"
        decision["next_teaching_action"] = "change_question"
    elif text:
        decision["student_message_intent"] = "answering_current_question"
        decision["next_teaching_action"] = "explain_then_check"

    expected_terms = set(
        word
        for word in re.findall(
            r"[a-zA-Z]+",
            " ".join([
                str(question.get("expected_answer") or ""),
                " ".join(str(k) for k in (question.get("keywords") or [])),
            ]).lower(),
        )
        if len(word) > 2
    )
    answer_terms = set(word for word in re.findall(r"[a-zA-Z]+", lowered) if len(word) > 2)
    if expected_terms and answer_terms:
        overlap = expected_terms & answer_terms
        if len(overlap) >= max(1, min(2, len(expected_terms))):
            decision["answer_quality"] = "partial"
            decision["matched_concepts"] = sorted(overlap)[:6]
            decision["missing_concepts"] = sorted(expected_terms - overlap)[:6]
    return decision


def decision_to_result_fields(decision: dict[str, Any]) -> dict[str, Any]:
    quality = str(decision.get("answer_quality") or "unclear")
    action = str(decision.get("next_teaching_action") or "")
    intent = str(decision.get("student_message_intent") or "unclear")

    if intent == "asking_direct_question":
        result_intent = "meta_question"
    elif intent == "off_topic":
        result_intent = "off_topic"
    elif intent in {"confused", "complaint", "unclear"}:
        result_intent = "confused"
    elif quality in {"correct", "partial", "wrong"}:
        result_intent = quality
    else:
        result_intent = "answer_attempt"

    understanding = {
        "correct": "strong",
        "partial": "partial",
        "wrong": "weak",
        "unclear": "unclear",
    }.get(quality, "unclear")

    if decision.get("should_move_next") and quality == "correct":
        recommended = "move_next"
    elif action in {"answer_directly", "explain_then_check", "correct_misconception", "give_example", "ask_easier_question"}:
        recommended = "clarify" if quality in {"wrong", "unclear"} else "ask_followup"
    elif action == "acknowledge_and_move_next" and decision.get("should_move_next") and quality == "correct":
        recommended = "move_next"
    elif action == "acknowledge_and_move_next":
        recommended = "ask_followup"
    elif action == "change_question":
        recommended = "move_next" if decision.get("should_move_next") else "ask_followup"
    else:
        recommended = "clarify"

    score_delta = {
        "correct": 10,
        "partial": 5,
        "wrong": 1,
        "unclear": 0,
    }.get(quality, 0)

    return {
        "intent": result_intent,
        "understanding_level": understanding,
        "missing_concepts": _safe_list(decision.get("missing_concepts"), 6),
        "misconception_tags": [],
        "recommended_next_action": recommended,
        "score_delta": score_delta,
    }


async def decide_tutor_turn(
    provider: Any,
    *,
    topic: str,
    session: dict[str, Any],
    question: dict[str, Any],
    student_message: str,
    retrieved_context: str,
    student_profile: dict[str, Any],
    progress: dict[str, Any],
    recent_learning_history: list[dict[str, Any]],
) -> dict[str, Any]:
    history = _compact_history(recent_learning_history, limit=4)
    previous_bot_question = _latest_bot_question(history)
    active_question = previous_bot_question or str(question.get("question_text") or "")

    system = (
        "You are AI-EZAM's topic-independent Tutor Decision Layer. "
        "You do not write the student-facing tutor reply. "
        "Your job is to semantically interpret the student's latest message against the active question, expected answer, keywords, concept, explanation, retrieved reference knowledge, and recent history. "
        "Use meaning, not exact word matching. Understand short answers, spelling mistakes, partial answers, direct questions, complaints, confusion, and requests to move on. "
        "If a student's spelling is close to a valid concept in the supplied context, infer the intended concept and do not treat the spelling mistake as a science error. "
        "The current student message has highest priority, the previous bot question has second priority, and the original lesson question has third priority. "
        "If the previous bot question exists, judge the student mainly against that question. "
        "Do not apply any topic-specific Python rule; use only the supplied question bank and knowledgebase context. "
        "Return valid JSON only."
    )
    user = f"""
Return exactly this JSON shape:
{{
  "student_message_intent": "answering_current_question | asking_direct_question | confused | complaint | off_topic | wants_to_move_on | unclear",
  "interpreted_student_meaning": "...",
  "active_question_answered": true,
  "answer_quality": "correct | partial | wrong | unclear",
  "matched_concepts": ["..."],
  "missing_concepts": ["..."],
  "should_repeat_question": false,
  "should_move_next": true,
  "must_explain_first": true,
  "next_teaching_action": "answer_directly | explain_then_check | acknowledge_and_move_next | correct_misconception | ask_easier_question | give_example | change_question",
  "reason_summary": "short safe explanation of decision"
}}

Decision rules:
- Treat answers in Tamil, English, or mixed language equally. Ignore grammar errors when the science meaning is clear.
- A question mark alone does not make an answer a request: "tiny living things?" can be a tentative answer.
- If a student requests a different question or wants to skip, choose change_question without awarding mastery for the skipped question.
- A comprehension check must stay attached to the same learning objective. Track what the student already understood before asking for a missing detail.
- If the student answered the active question sufficiently, set active_question_answered true and do not repeat the same question.
- If the student asks a direct question, mark asking_direct_question, choose answer_directly, and set must_explain_first true unless it is off topic.
- If the student says they do not know, asks for help, asks the tutor to give the answer, says the question is hard, or shows confusion, choose explain_then_check and set must_explain_first true.
- If the student complains about repetition, boredom, too many words, unclear wording, or missing choices, treat it as complaint, set must_explain_first true unless moving next, and decide whether to clarify, change question, or move next based on history.
- If the student gives a wrong answer, choose correct_misconception.
- If the student gives a partially correct answer, list matched and missing concepts.
- Treat recognizable spelling mistakes as the intended concept when the meaning is clear from the supplied context.
- Do not mark an answer wrong only because a valid concept is misspelled; normalize the intended meaning in interpreted_student_meaning.
- If the active question asks for examples, methods, choices, or items, judge the student's listed items semantically against keywords and retrieved context; do not require the expected answer sentence to be repeated.
- If the student gives enough plausible examples/items for that active question, mark the active question answered even when spelling is imperfect.
- If the active question asks "What is ..." or asks for a definition, mark correct when the student states the main meaning or purpose from expected_answer/explanation/context.
- For definition questions, do not require examples, methods, types, or extra details unless the question explicitly asks for them.
- missing_concepts must include only concepts required by the active question, not extra examples imported from retrieved context.
- If the active question asks for a definition and the student gives only valid examples from the supplied context, mark partial instead of wrong.
- If the active question asks for examples and the student gives valid examples from the supplied context, mark correct or partial based on how many examples the question asks for.
- If the active question asks why/how and the student gives only an example, mark partial unless the example also explains the reason.
- If the student's answer is in the right direction but contains a science precision error, contradiction, or misconception compared with expected_answer/explanation/context, mark partial or wrong, not correct.
- Do not mark fully correct when important wording changes the science meaning, even if some keywords match.
- When precision is partial or wrong, identify the exact relationship that needs correction in reason_summary so the tutor can explain that detail.
- Before saying a concept is missing, check whether the student already supplied it in the current message or recent history.
- If the student wants to move on, allow should_move_next only when the supplied history shows sufficient understanding of the active concept.
- Use the expected answer, keywords, explanation, misconception tag, and reference knowledge as topic knowledge.
- Do not invent topic facts that are not supported by the question/context.
- Do not write any student-visible bilingual response.

Topic:
{topic}

Session:
{json.dumps({"mode": session.get("mode"), "current_concept": session.get("current_concept")}, ensure_ascii=False)}

Original lesson question:
{json.dumps(_question_context(question), ensure_ascii=False)}

Previous bot question / active question:
{active_question}

Student message:
{student_message}

Recent learning history:
{json.dumps(history, ensure_ascii=False)}

Student profile:
{json.dumps({"name": student_profile.get("name", "")}, ensure_ascii=False)}

Progress summary:
{json.dumps(progress, ensure_ascii=False)[:1000]}

Reference knowledge:
{_short_text(retrieved_context, 1200)}
"""
    try:
        raw = await _chat_json(provider, system, user)
        return _coerce_decision(raw)
    except Exception as exc:
        raise RuntimeError("The tutor could not evaluate this answer. Please try again.") from exc
