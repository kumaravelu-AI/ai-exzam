from __future__ import annotations
from typing import Any
import json
import os
import re
import httpx

from .config import AI_PROVIDER
from .response_formatter import (
    _bilingual_message,
    _extract_first_question_line,
    _split_bilingual_message,
    _student_visible_reply_from_fields,
    validate_and_format_response,
)
from .guardrail_repair import (
    _apply_tutor_guardrails,
    _fallback_from_question,
    _looks_confused,
    _looks_strongly_confused,
    _recent_followup_questions,
    _reply_quality_issues,
    _strip_json_fence,
    _synthesized_options,
)
from .tamil_naturalizer import naturalize_tamil_fields_with_context, naturalize_visible_reply
from .tutor_decision import decide_tutor_turn, decision_to_result_fields


AI_DEBUG = os.getenv("AI_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

DEFAULT_TUTOR_RESPONSE = {
    "student_visible_reply": (
        "No problem, I will explain the idea simply.\n\n"
        "Can you try one short answer?\n\n"
        "பரவாயில்லை, இந்த கருத்தை எளிதாக விளக்குகிறேன்.\n\n"
        "ஒரு சுருக்கமான பதிலை முயற்சி செய்ய முடியுமா?"
    ),
    "intent": "answer_attempt",
    "understanding_level": "unclear",
    "missing_concepts": [],
    "misconception_tags": [],
    "recommended_next_action": "clarify",
    "score_delta": 0,
}


def _safe_int(value: Any, fallback: int = 0) -> int:
    if value is None:
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_tutor_result(data: dict[str, Any]) -> dict[str, Any]:
    result = dict(DEFAULT_TUTOR_RESPONSE)
    structured_reply = _student_visible_reply_from_fields(data)
    intent = str(data.get("intent") or result["intent"]).strip()
    if intent == "mixed":
        intent = "partial"
    understanding = str(data.get("understanding_level") or result["understanding_level"]).strip()
    if understanding == "medium":
        understanding = "partial"
    if understanding == "high":
        understanding = "strong"
    action = str(data.get("recommended_next_action") or "").strip()
    if not action:
        action = {
            "correct": "move_next",
            "partial": "ask_followup",
            "wrong": "reteach",
            "confused": "clarify",
            "off_topic": "clarify",
            "meta_question": "clarify",
        }.get(intent, result["recommended_next_action"])
    result.update({
        "student_visible_reply": str(structured_reply or data.get("student_visible_reply") or result["student_visible_reply"]).strip(),
        "intent": intent,
        "understanding_level": understanding,
        "missing_concepts": [str(x).strip() for x in (data.get("missing_concepts") or []) if str(x).strip()][:6],
        "misconception_tags": [str(x).strip() for x in (data.get("misconception_tags") or []) if str(x).strip()][:6],
        "recommended_next_action": action,
        "score_delta": _safe_int(data.get("score_delta"), int(result["score_delta"])),
    })
    return result


def _prompt_question_context(question: dict[str, Any]) -> dict[str, Any]:
    context = {
        "question_id": question.get("question_id"),
        "question_text": question.get("question_text"),
        "question_type": question.get("question_type"),
        "expected_answer": question.get("expected_answer"),
        "keywords": question.get("keywords") or [],
        "concept": question.get("concept"),
        "hint": question.get("hint"),
        "explanation": question.get("explanation"),
        "misconception_tag": question.get("misconception_tag"),
    }
    options = _synthesized_options(question)
    if options:
        context["available_options"] = options
    return context


def _latest_tutor_question(recent_learning_history: list[dict[str, Any]]) -> str:
    for item in reversed(recent_learning_history or []):
        prior = str(item.get("tutor_reply") or item.get("feedback") or "").strip()
        parts = _split_bilingual_message(prior)
        if parts:
            return parts[1]
        question = _extract_first_question_line(prior, "")
        if question:
            return question
    return ""


def _short_text(text: str, limit: int = 800) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _compact_history(items: list[dict[str, Any]], limit: int = 2) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in (items or [])[-limit:]:
        compact.append({
            "question_text": item.get("question_text", ""),
            "student_answer": item.get("student_answer", ""),
            "analysis": item.get("analysis", {}),
            "tutor_reply": item.get("tutor_reply") or item.get("feedback", ""),
        })
    return compact


def _text_terms(text: str) -> set[str]:
    stop_words = {
        "the", "and", "are", "you", "your", "this", "that", "what", "why", "how",
        "can", "could", "would", "one", "some", "with", "from", "about", "answer",
        "question", "tell", "name", "give", "try", "which", "does", "do",
    }
    return {
        word
        for word in re.findall(r"[a-zA-Z]+", (text or "").lower())
        if len(word) > 2 and word not in stop_words
    }


def _near_same_text(first: str, second: str) -> bool:
    first_norm = re.sub(r"\s+", " ", (first or "").strip().lower())
    second_norm = re.sub(r"\s+", " ", (second or "").strip().lower())
    if not first_norm or not second_norm:
        return False
    if first_norm == second_norm:
        return True
    first_terms = _text_terms(first_norm)
    second_terms = _text_terms(second_norm)
    if not first_terms or not second_terms:
        return False
    overlap = len(first_terms & second_terms) / max(1, min(len(first_terms), len(second_terms)))
    return overlap >= 0.75


def _debug_info(provider: Any, *, fallback_used: bool, error_type: str = "") -> dict[str, Any]:
    return {
        "provider": AI_PROVIDER,
        "model": getattr(provider, "model", "mock"),
        "base_url": getattr(provider, "base_url", "mock"),
        "fallback_used": fallback_used,
        "error_type": error_type or "",
    }


def _attach_debug(provider: Any, payload: dict[str, Any], *, fallback_used: bool, error_type: str = "") -> dict[str, Any]:
    if AI_DEBUG:
        payload["_debug"] = _debug_info(provider, fallback_used=fallback_used, error_type=error_type)
        print(f"AI_DEBUG {json.dumps(payload['_debug'], ensure_ascii=False)}")
    return payload


def _explain_first_issues(data: dict[str, Any], decision: dict[str, Any], question: dict[str, Any]) -> list[str]:
    if not decision.get("must_explain_first"):
        return []
    english_response = str(data.get("english_response") or "").strip()
    english_followup = str(data.get("english_followup") or "").strip()
    lowered = english_response.lower()
    followup_lowered = english_followup.lower()
    issues: list[str] = []
    transition_only = (
        "let's break" in lowered
        or lowered in {"let me explain.", "let me show you.", "no problem.", "i can help."}
        or lowered.startswith("let's look")
        or lowered.startswith("we can ")
    )
    has_explanation_signal = any(
        token in lowered
        for token in (
            " is ",
            " are ",
            " means ",
            " because ",
            " answer ",
            " use ",
            " helps ",
            " happens ",
            " should ",
            " not ",
        )
    )
    if not english_response or transition_only or not has_explanation_signal:
        issues.append("Decision requires explain-first: english_response must give a direct answer or explanation, not only a transition phrase.")
    if _near_same_text(english_followup, str(question.get("question_text") or "")):
        issues.append("Decision requires explain-first: english_followup must not repeat the original question; ask an easier check based on the explanation.")
    if str(decision.get("student_message_intent") or "").strip().lower() in {"confused", "complaint"}:
        if "what do you think" in followup_lowered or "can you think" in followup_lowered:
            issues.append("Confused students need a direct example/check question, not a 'what do you think' prompt.")
        if not any(token in lowered for token in ("example", "for example", "like ", "such as")):
            issues.append("Confused students should get one concrete example in the English response when the context supports one.")
    return issues


def _reference_guidance(topic: str, question: dict[str, Any]) -> str:
    return (
        "Use only the current question, expected answer, keywords, concept, explanation, misconception tag, recent history, and retrieved knowledge as topic reference. "
        "Do not rely on hardcoded examples or fixed replies."
    )


async def _chat_tutor_json(provider: Any, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    text = await provider.chat(system_prompt, user_prompt)
    try:
        return json.loads(_strip_json_fence(text))
    except json.JSONDecodeError:
        repair_prompt = f"""
Repair this model output into valid JSON only.
Keep these exact keys:
intent,
understanding_level,
english_response,
english_followup,
tamil_response,
tamil_followup,
score_delta

Do not add markdown or comments.

Broken output:
{text}
"""
        repaired = await provider.chat(
            "You repair malformed JSON. Return valid JSON only.",
            repair_prompt,
        )
        return json.loads(_strip_json_fence(repaired))


async def _repair_tutor_json(
    provider: Any,
    *,
    original_data: dict[str, Any],
    issues: list[str],
    question: dict[str, Any],
    student_message: str,
    recent_learning_history: list[dict[str, Any]],
    decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repair_prompt = f"""
The previous tutor JSON has these quality problems:
{json.dumps(issues, ensure_ascii=False)}

Rewrite the JSON only. Keep exactly these keys:
intent,
understanding_level,
english_response,
english_followup,
tamil_response,
tamil_followup,
score_delta

Rules:
- keep the same visible four-part bilingual format through these fields
- be accurate and specific to the student's exact answer
- give highest priority to the current student message
- never say the student mentioned, listed, gave, or provided examples unless those exact ideas are in the current student message or recent history
- facts from the reference context can be taught, but must not be described as something the student already said
- answer direct student questions directly before returning to lesson flow
- if the decision says must_explain_first, the English response must contain a direct answer or explanation before the follow-up
- if the decision says must_explain_first, the English follow-up must be an easier check question and must not repeat the original question
- do not rephrase the original question by adding "what do you think"; ask a smaller check question based on the explanation
- if the student is confused or asks for the answer, include one concrete example from the supplied context when available
- do not ask "what do you think" or "can you think of" after confusion; ask a simple check based on the example
- explain what the student got right and what needs correction before asking the next check question
- use ask_followup or clarify to check the same concept again; use move_next only when the student is clearly ready
- if the student is confused on multiple choice, include the choices in the follow-up
- if the student says they do not know, do not understand, do not get you, or asks "you tell me", give the answer directly before asking a check question
- if the student complains, is bored, or says there are too many words, use short mode: one direct sentence, one simple example if useful, and one easy check question
- if the student complains that you asked a different question, acknowledge briefly and explain the current question in simpler words
- do not ask "Can you think of..." after a confused or repeated-confusion message; give one simple example first
- judge mixed answers part by part
- use topic facts only from the current question, expected answer, keywords, explanation, misconception tag, recent history, and reference knowledge
- do not mark a precise-but-incomplete or partly wrong science idea as fully correct
- for example/list/method questions, accept semantically correct listed items even when spelling is imperfect
- for definition questions, accept a meaning or purpose answer when it matches the expected answer; do not demand examples unless the active question asks for examples
- when correcting a precision issue, explain the exact relationship that was wrong instead of replacing it with a broad topic summary
- do not use backend scoring phrases such as "captures the basic meaning", "provided a correct answer", or "matches the concept"
- Tamil must be natural school-level Tamil that matches the English meaning, not literal word-by-word translation
- avoid awkward Tamil such as புலன் கண்களால், நீங்கள் யாக இருக்கிறீர்கள், உங்கள் கருத்தில் எடுத்துக்கொள்ளுங்களா, and உங்களுக்கு எண்ணம் வருகிறதா
- no markdown, no headings, no extra keys

Current question:
{json.dumps(_prompt_question_context(question), ensure_ascii=False)}

Student message:
{student_message}

Recent learning history:
{json.dumps(_compact_history(recent_learning_history, limit=4), ensure_ascii=False)}

Tutor decision:
{json.dumps(decision or {}, ensure_ascii=False)}

Previous JSON:
{json.dumps(original_data, ensure_ascii=False)}
"""
    return await _chat_tutor_json(
        provider,
        "You fix tutor JSON for accuracy, natural Tamil, and concise teaching. Return valid JSON only.",
        repair_prompt,
    )


async def mock_tutor_turn(
    *,
    question: dict[str, Any],
    student_message: str,
    recent_learning_history: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = (question.get("expected_answer") or "").lower().strip()
    answer = student_message.lower().strip()
    keywords = [k.strip() for k in expected.replace(";", ",").split(",") if k.strip()]
    hit_count = sum(1 for k in keywords if k.lower() in answer) if keywords else 0
    if not answer or _looks_strongly_confused(student_message):
        level = "unclear"
        action = "clarify"
        score = 0
        intent = "confusion"
    elif _looks_confused(student_message):
        level = "unclear"
        action = "clarify"
        score = 0
        intent = "confusion"
    elif "?" in student_message and len(answer.split()) < 12:
        level = "unclear"
        action = "clarify"
        score = 0
        intent = "clarification_request"
    elif keywords and hit_count >= max(1, len(keywords) // 2 + len(keywords) % 2):
        level = "strong"
        action = "move_next"
        score = 12
        intent = "answer_attempt"
    elif keywords and hit_count > 0:
        level = "partial"
        action = "ask_followup"
        score = 6
        intent = "answer_attempt"
    else:
        level = "weak"
        action = "reteach"
        score = 2
        intent = "answer_attempt"

    missing = [k for k in keywords if k.lower() not in answer][:3]
    fallback_response, fallback_question = _fallback_from_question(
        question,
        confused=intent == "confusion",
    )
    if intent == "confusion":
        reply = validate_and_format_response(
            "",
            fallback_response=fallback_response,
            fallback_question=fallback_question,
        )
    elif level == "strong":
        reply = _bilingual_message(
            "Good, you got the main idea.",
            "சரி, முக்கிய கருத்தை நீங்கள் புரிந்து கொண்டீர்கள்.",
            "Can you try the next question?",
            "அடுத்த கேள்வியை முயற்சிக்க முடியுமா?",
        )
    elif action == "clarify":
        reply = validate_and_format_response(
            "",
            fallback_response=fallback_response,
            fallback_question=fallback_question,
        )
    elif action == "ask_followup":
        reply = _bilingual_message(
            "Almost. One detail is missing.",
            "கிட்டத்தட்ட சரி. இன்னொரு தகவல் தேவை.",
            "Can you add that detail?",
            "அந்த தகவலை சேர்க்க முடியுமா?",
        )
    else:
        reply = validate_and_format_response(
            "",
            fallback_response=fallback_response,
            fallback_question=fallback_question,
        )

    result = _coerce_tutor_result({
        "student_visible_reply": reply,
        "intent": intent,
        "understanding_level": level,
        "missing_concepts": missing,
        "misconception_tags": ["incomplete_understanding"] if missing else [],
        "recommended_next_action": action,
        "score_delta": score,
    })
    return _apply_tutor_guardrails(
        result=result,
        question=question,
        student_message=student_message,
        recent_learning_history=recent_learning_history,
    )


async def tutor_turn(provider: Any, *, topic: str, session: dict[str, Any], question: dict[str, Any],
                     student_message: str, retrieved_context: str, student_profile: dict[str, Any],
                     progress: dict[str, Any], recent_learning_history: list[dict[str, Any]]) -> dict[str, Any]:
    """Interpret, teach and translate together so each turn has one coherent decision."""
    if AI_PROVIDER == "mock":
        return await mock_tutor_turn(question=question, student_message=student_message,
                                     recent_learning_history=recent_learning_history)
    from .tutor_decision import _coerce_decision
    system = """You are a warm Malaysian Year 6 science tutor. Return JSON only.
Interpret meaning, including imperfect grammar, spelling, Tamil and English. Never demand exact phrases.
Use the last tutor question and original lesson objective together. Accept a correct original definition even after an easier check.
Do not mark contradictions correct because keywords overlap. A tentative answer ending '?' is still an answer.
Teach before checking when confused: explain simply with one supported example, then ask ONE easier question.
The check must be answerable from the explanation you just gave. Do not ask for examples unless you supplied one.
Use பரவாயில்லை for reassurance, சரி for correctness, and வெறும் கண்களால் for naked eyes.
Answer direct questions first. For a partial answer explain only the missing essential idea. For complaints acknowledge and adapt.
When correct, acknowledge what is right and set should_move_next=true. Do not repeat the question or demand optional details.
When the learner asks to skip, use wants_to_move_on and change_question; do not award understanding.
Use supplied reference knowledge. Generic question-bank placeholders are not scientific answers.
Tamil explanation and question MUST convey the same facts, examples, negation, and question as English. No generic Tamil filler.
Keep each explanation to two short sentences, each followup to one question. Never show internal reasoning.
Return keys english_response, tamil_response, english_followup, tamil_followup, and tutor_decision.
tutor_decision keys: student_message_intent (answering_current_question, asking_direct_question, confused, complaint, off_topic, wants_to_move_on),
answer_quality (correct, partial, wrong, unclear), active_question_answered (boolean), should_move_next (boolean),
should_repeat_question (false), must_explain_first (boolean), matched_concepts (array), missing_concepts (array),
next_teaching_action (acknowledge_and_move_next, explain_then_check, answer_directly, correct_misconception, change_question), reason_summary (short).
Do not consider greetings, requests for help, or skipping as evidence of mastery."""
    user = json.dumps({"topic": topic, "question": _prompt_question_context(question),
                       "student_message": student_message,
                       "history": _compact_history(recent_learning_history, limit=3),
                       "reference": retrieved_context[:2200]}, ensure_ascii=False)
    try:
        raw = await _chat_tutor_json(provider, system, user)
        decision = _coerce_decision(raw["tutor_decision"])
        for key in ("english_response", "english_followup", "tamil_response", "tamil_followup"):
            if not isinstance(raw.get(key), str) or not raw[key].strip():
                raise ValueError("Missing bilingual teaching field")
        for key in ("tamil_response", "tamil_followup"):
            if not re.search(r"[\u0b80-\u0bff]", raw[key]):
                raise ValueError("Missing Tamil translation")
        result = _coerce_tutor_result(raw)
        result.update(decision_to_result_fields(decision))
        result["tutor_decision"] = decision
        return result
    except Exception as exc:
        raise RuntimeError("The tutor could not produce a reliable bilingual response.") from exc




async def mock_score_exam_answer(question: dict[str, Any], student_answer: str) -> dict[str, Any]:
    expected = (question.get("expected_answer") or "").lower().strip()
    answer = student_answer.lower().strip()
    keywords = [k.strip() for k in expected.replace(";", ",").split(",") if k.strip()]
    max_marks = int(question.get("marks", 1) or 1)
    hit_count = sum(1 for k in keywords if k.lower() in answer) if keywords else 0

    if not answer:
        understanding = "wrong"
        score = 0
    elif keywords and hit_count >= max(1, len(keywords) // 2 + len(keywords) % 2):
        understanding = "strong"
        score = max_marks
    elif keywords and hit_count > 0:
        understanding = "partial"
        score = max(1, max_marks // 2)
    else:
        understanding = "wrong"
        score = 0

    return {
        "score_awarded": score,
        "max_marks": max_marks,
        "understanding_level": understanding,
        "missing_concepts": [k for k in keywords if k.lower() not in answer][:3],
        "misconception_tags": ["semantic_miss"] if score < max_marks else [],
        "student_visible_reply": "Answer recorded.",
    }


async def score_exam_answer(
    provider: Any,
    *,
    topic: str,
    question: dict[str, Any],
    student_answer: str,
    retrieved_context: str,
    student_profile: dict[str, Any],
    progress: dict[str, Any],
    recent_exam_history: list[dict[str, Any]],
) -> dict[str, Any]:
    if AI_PROVIDER == "mock":
        result = await mock_score_exam_answer(question, student_answer)
        return _attach_debug(provider, result, fallback_used=True)

    system = (
        "You are an exam scoring engine. "
        "Judge answers semantically against the expected answer and reference knowledge. "
        "Always make student_visible_reply bilingual in English and Tamil. "
        "English and Tamil must be on separate lines. "
        "Return valid JSON only."
    )
    short_context = _short_text(retrieved_context, limit=1200)
    short_history = _compact_history(recent_exam_history, limit=2)
    user = f"""
Return JSON with exactly these keys:
score_awarded,
max_marks,
understanding_level,
missing_concepts,
misconception_tags,
student_visible_reply

Allowed understanding_level values:
strong | partial | weak | wrong | unclear

Question:
{json.dumps({
    "question_id": question.get("question_id"),
    "question_text": question.get("question_text"),
    "expected_answer": question.get("expected_answer"),
    "marks": question.get("marks"),
    "concept": question.get("concept"),
}, ensure_ascii=False)}

Student answer:
{student_answer}

Recent exam history:
{json.dumps(short_history, ensure_ascii=False)}

Reference knowledge for scoring use only:
{short_context}
"""
    try:
        text = await provider.chat(system, user)
        data = json.loads(_strip_json_fence(text))
        max_marks = int(question.get("marks", 1) or 1)
        score_awarded = max(0, min(max_marks, int(data.get("score_awarded", 0))))
        result = {
            "score_awarded": score_awarded,
            "max_marks": max_marks,
            "understanding_level": str(data.get("understanding_level") or "unclear"),
            "missing_concepts": [str(x).strip() for x in (data.get("missing_concepts") or []) if str(x).strip()][:6],
            "misconception_tags": [str(x).strip() for x in (data.get("misconception_tags") or []) if str(x).strip()][:6],
            "student_visible_reply": str(data.get("student_visible_reply") or "Answer recorded.").strip(),
        }
        return _attach_debug(provider, result, fallback_used=False)
    except (httpx.TimeoutException, httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError, KeyError, RuntimeError) as exc:
        fallback = await mock_score_exam_answer(question, student_answer)
        return _attach_debug(provider, fallback, fallback_used=True, error_type=type(exc).__name__)


async def mock_clarify() -> str:
    return validate_and_format_response(
        "",
        fallback_response="This idea can be explained in one simple step.",
        fallback_question="Can you say one key point from the lesson?",
    )


async def clarify(provider: Any, *, ask: str, retrieved_context: str, topic: str) -> str:
    if AI_PROVIDER == "mock":
        return await mock_clarify()

    system = (
        "You are a lively student tutor. "
        "Give a short simple explanation in both English and Tamil. "
        "English and Tamil must be on separate lines. "
        "Use this format only: English explanation, blank line, English question, blank line, Tamil explanation, blank line, Tamil question. "
        "Be engaging and not too long."
    )
    user = f"""
Topic: {topic}
Student asks: {ask}

Use this reference:
{retrieved_context[:4000]}
"""
    text = await provider.chat(system, user)
    return validate_and_format_response(
        text,
        fallback_response="This idea needs one simple fact to remember.",
        fallback_question="Can you tell me that fact now?",
    )
