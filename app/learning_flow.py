from __future__ import annotations
from typing import Any
import re

from .models import ChatRequest
from .student_tracker import (
    save_current_session,
    append_learning_history,
    update_topic_progress,
    snapshot_student,
    get_progress,
    save_progress,
    now_iso,
)
from .teaching_engine import choose_next_question, tutor_learning_turn, translate_question_to_tamil
from .scoring_engine import score_analysis
from .guardrail_repair import _format_options_question
from .tutor_decision import decision_to_result_fields


GENERIC_TAMIL_QUESTION = "மேலுள்ள கேள்விக்கு சுருக்கமாக பதில் சொல்ல முடியுமா?"


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


def _tamil_question(question: dict[str, Any]) -> str:
    tamil_question = str(question.get("tamil_question") or question.get("question_text_ta") or "").strip()
    if tamil_question:
        return tamil_question
    return GENERIC_TAMIL_QUESTION


async def _display_question_pair(subject: str, level: str, topic: str, question: dict[str, Any]) -> tuple[str, str]:
    question_text = str(question.get("question_text") or "").strip()
    if str(question.get("question_type") or "").strip().lower() == "mcq":
        english_question, tamil_question = _format_options_question(question)
        explicit_tamil = str(question.get("tamil_question") or question.get("question_text_ta") or "").strip()
        if explicit_tamil:
            return english_question, explicit_tamil
        return english_question, await translate_question_to_tamil(subject, level, topic, english_question)
    explicit_tamil = _tamil_question(question)
    if explicit_tamil != GENERIC_TAMIL_QUESTION:
        return question_text, explicit_tamil
    return question_text, await translate_question_to_tamil(subject, level, topic, question_text)


def _split_bilingual_message(text: str) -> tuple[str, str, str, str] | None:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if len(lines) < 4:
        return None
    return lines[0], lines[1], lines[2], lines[3]


def _english_followup(text: str) -> str:
    parts = _split_bilingual_message(text)
    if parts:
        return parts[1]
    match = re.search(r"[^.!?]*\?", text or "")
    return match.group(0).strip() if match else ""


def _question_terms(text: str) -> set[str]:
    stop_words = {
        "the",
        "and",
        "are",
        "you",
        "your",
        "this",
        "that",
        "what",
        "why",
        "how",
        "can",
        "could",
        "would",
        "one",
        "some",
        "with",
        "from",
        "about",
        "answer",
        "question",
    }
    return {
        word
        for word in re.findall(r"[a-zA-Z]+", (text or "").lower())
        if len(word) > 2 and word not in stop_words
    }


def _near_same_question(first: str, second: str) -> bool:
    first_norm = re.sub(r"\s+", " ", (first or "").strip().lower())
    second_norm = re.sub(r"\s+", " ", (second or "").strip().lower())
    if not first_norm or not second_norm:
        return False
    if first_norm == second_norm:
        return True
    first_terms = _question_terms(first_norm)
    second_terms = _question_terms(second_norm)
    if not first_terms or not second_terms:
        return False
    # Sharing a topic noun does not make a simpler check the same question.
    from difflib import SequenceMatcher
    return SequenceMatcher(None, first_norm, second_norm).ratio() >= 0.92


def _session_learning_history(student_id: str, session: dict[str, Any]) -> list[dict[str, Any]]:
    snap = snapshot_student(student_id)
    items = snap.get("learning_history", []) or []
    started_at = str(session.get("started_at") or "")
    subject = session.get("subject")
    level = session.get("level")
    topic = session.get("topic")

    current_items: list[dict[str, Any]] = []
    for item in items:
        if subject and item.get("subject") != subject:
            continue
        if level and item.get("level") != level:
            continue
        if topic and item.get("topic") != topic:
            continue
        if started_at and item.get("session_started_at") != started_at:
            continue
        current_items.append(item)
    return current_items[-6:]


def _recent_bot_questions(history: list[dict[str, Any]]) -> list[str]:
    questions: list[str] = []
    for item in history:
        question = _english_followup(str(item.get("tutor_reply") or item.get("feedback") or ""))
        if question:
            questions.append(question)
    return questions


def _important_missing_concepts(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    ignored = {"", "none", "n/a", "na", "not important", "minor", "minor detail", "optional"}
    return [str(item).strip() for item in value if str(item).strip().lower() not in ignored]


def _decision_quality(tutor_decision: dict[str, Any], analysis: dict[str, Any]) -> str:
    return str(tutor_decision.get("answer_quality") or analysis.get("understanding_level") or "unclear").strip().lower()


def _decision_intent(tutor_decision: dict[str, Any], analysis: dict[str, Any]) -> str:
    return str(tutor_decision.get("student_message_intent") or analysis.get("intent") or "").strip().lower()


def should_advance_from_decision(tutor_decision: dict[str, Any], analysis: dict[str, Any]) -> bool:
    if not isinstance(tutor_decision, dict) or not tutor_decision:
        return False

    intent = str(tutor_decision.get("student_message_intent") or "").strip().lower()
    quality = str(tutor_decision.get("answer_quality") or "").strip().lower()
    active_answered = tutor_decision.get("active_question_answered") is True
    repeat = tutor_decision.get("should_repeat_question") is True
    missing_source = tutor_decision.get("missing_concepts") if "missing_concepts" in tutor_decision else analysis.get("missing_concepts")
    missing = _important_missing_concepts(missing_source)

    if intent in {"asking_direct_question", "off_topic", "confused"}:
        return False
    return quality == "correct" and active_answered and not repeat and not missing


def _recent_support_needed_count(history: list[dict[str, Any]]) -> int:
    count = 0
    for item in history:
        analysis = item.get("analysis") or {}
        intent = str(analysis.get("intent") or "").strip().lower()
        level = str(analysis.get("understanding_level") or "").strip().lower()
        action = str(analysis.get("recommended_next_action") or "").strip().lower()
        if intent in {"confused", "confusion", "meta_question"} or level in {"weak", "wrong", "unclear"} or action in {"clarify", "reteach"}:
            count += 1
    return count


def _concept_status_from_turn(tutor_decision: dict[str, Any], analysis: dict[str, Any], support_count: int) -> str:
    intent = _decision_intent(tutor_decision, analysis)
    quality = _decision_quality(tutor_decision, analysis)
    must_explain = tutor_decision.get("must_explain_first") is True
    if intent in {"confused", "asking_direct_question", "off_topic"} or quality in {"wrong", "unclear"}:
        return "weak"
    if quality == "correct" and not must_explain and support_count == 0:
        return "strong"
    if quality == "correct":
        return "partial"
    if quality == "partial":
        return "partial"
    return "unknown"


def _effective_score_delta(
    tutor_decision: dict[str, Any],
    analysis: dict[str, Any],
    *,
    support_count: int,
) -> int:
    raw = int(analysis.get("score_delta") or 0)
    if tutor_decision.get("student_message_intent") == "wants_to_move_on":
        return 0
    intent = _decision_intent(tutor_decision, analysis)
    quality = _decision_quality(tutor_decision, analysis)
    must_explain = tutor_decision.get("must_explain_first") is True

    if intent in {"confused", "asking_direct_question", "off_topic"} or quality in {"wrong", "unclear"}:
        return 0
    if quality == "partial":
        return min(raw, 5)
    if must_explain or support_count >= 2:
        return min(raw, 6)
    return raw


def _update_concept_status(
    student_id: str,
    *,
    subject: str,
    level: str,
    topic: str,
    concept: str,
    status: str,
    cap_mastery: int | None = None,
) -> dict[str, Any]:
    progress = get_progress(student_id)
    topic_ref = progress.setdefault("subjects", {}).setdefault(subject, {}).setdefault(level, {}).setdefault(topic, {})
    statuses = topic_ref.setdefault("concept_statuses", {})
    rank = {"unknown": 0, "weak": 1, "partial": 2, "strong": 3}
    current = str(statuses.get(concept) or "unknown")
    if rank.get(status, 0) >= rank.get(current, 0):
        statuses[concept] = status
    elif status == "weak" and current == "unknown":
        statuses[concept] = "weak"

    if cap_mastery is not None:
        topic_ref["topic_mastery"] = min(int(topic_ref.get("topic_mastery") or 0), cap_mastery)
        if int(topic_ref.get("topic_mastery") or 0) < 60:
            topic_ref["ready_for_exam"] = False
    save_progress(student_id, progress)
    return topic_ref


def _decision_blocks_advance(tutor_decision: dict[str, Any]) -> bool:
    if not isinstance(tutor_decision, dict) or not tutor_decision:
        return False
    intent = str(tutor_decision.get("student_message_intent") or "").strip().lower()
    quality = str(tutor_decision.get("answer_quality") or "").strip().lower()
    if intent in {"asking_direct_question", "off_topic", "confused"}:
        return True
    return quality in {"wrong", "unclear"}


def _followup_repeats_recent(feedback: str, recent_questions: list[str]) -> bool:
    followup = _english_followup(feedback)
    return bool(followup) and any(_near_same_question(followup, prior) for prior in recent_questions)


def _followup_repeats_active_question(feedback: str, question: dict[str, Any]) -> bool:
    followup = _english_followup(feedback)
    return bool(followup) and _near_same_question(followup, str(question.get("question_text") or ""))


def _non_repeated_followup(question: dict[str, Any], recent_questions: list[str]) -> tuple[str, str]:
    candidates = [
        (
            "Can you say it in one simple sentence?",
            "அதை ஒரு எளிய வாக்கியத்தில் சொல்ல முடியுமா?",
        ),
        (
            "Can you answer it in an easier way?",
            "இதை இன்னும் எளிதாக சொல்ல முடியுமா?",
        ),
        (
            "Can you use the hint to say the main idea?",
            "குறிப்பைப் பார்த்து முக்கிய கருத்தை சொல்ல முடியுமா?",
        ),
    ]
    if str(question.get("hint") or "").strip():
        candidates.insert(0, candidates.pop(2))
    for english, tamil in candidates:
        if not any(_near_same_question(english, prior) for prior in recent_questions):
            return english, tamil
    return candidates[0]


def _replace_question_block(text: str, english_question: str, tamil_question: str) -> str:
    parts = _split_bilingual_message(text)
    if not parts:
        return text
    english_explanation, _, tamil_explanation, _ = parts
    return _bilingual_message(
        english_explanation,
        tamil_explanation,
        english_question,
        tamil_question,
    )


def _append_learning_turn(
    student_id: str,
    *,
    session: dict[str, Any],
    question: dict[str, Any],
    student_message: str,
    analysis: dict[str, Any],
    tutor_reply: str,
) -> None:
    append_learning_history(student_id, {
        "timestamp": now_iso(),
        "subject": session["subject"],
        "level": session["level"],
        "topic": session["topic"],
        "session_started_at": session.get("started_at"),
        "question_id": question["question_id"],
        "question_text": question["question_text"],
        "student_answer": student_message,
        "analysis": analysis,
        "tutor_reply": tutor_reply,
    })


async def handle_learning_message(payload: ChatRequest, session: dict[str, Any], question: dict[str, Any]) -> dict[str, Any]:
    subject = session["subject"]
    level = session["level"]
    topic = session["topic"]
    recent_history = _session_learning_history(payload.student_id, session)
    recent_questions = _recent_bot_questions(recent_history)

    llm_result = await tutor_learning_turn(
        student_id=payload.student_id,
        subject=subject,
        level=level,
        topic=topic,
        session=session,
        question=question,
        student_message=payload.message,
    )

    analysis = {
        "intent": llm_result.get("intent"),
        "understanding_level": llm_result.get("understanding_level"),
        "missing_concepts": llm_result.get("missing_concepts", []),
        "misconception_tags": llm_result.get("misconception_tags", []),
        "recommended_next_action": llm_result.get("recommended_next_action"),
        "score_delta": llm_result.get("score_delta", 0),
        "concept": question.get("concept") or session.get("current_concept") or "general",
    }
    tutor_decision = llm_result.get("tutor_decision") if isinstance(llm_result.get("tutor_decision"), dict) else {}
    if tutor_decision:
        decision_fields = decision_to_result_fields(tutor_decision)
        for key in ("intent", "understanding_level", "missing_concepts", "recommended_next_action", "score_delta"):
            analysis[key] = decision_fields.get(key, analysis.get(key))
            llm_result[key] = analysis[key]
    decision_advance = should_advance_from_decision(tutor_decision, analysis)
    if decision_advance:
        analysis["intent"] = "correct"
        analysis["understanding_level"] = "strong"
        analysis["recommended_next_action"] = "move_next"
        analysis["missing_concepts"] = []
        analysis["score_delta"] = max(int(analysis.get("score_delta") or 0), 10)
        llm_result["intent"] = analysis["intent"]
        llm_result["understanding_level"] = analysis["understanding_level"]
        llm_result["recommended_next_action"] = analysis["recommended_next_action"]
        llm_result["missing_concepts"] = analysis["missing_concepts"]
        llm_result["score_delta"] = analysis["score_delta"]
    feedback = llm_result.get("student_visible_reply", "")
    concept = analysis["concept"]
    support_count = _recent_support_needed_count(recent_history)
    status = _concept_status_from_turn(tutor_decision, analysis, support_count)
    analysis["score_delta"] = _effective_score_delta(tutor_decision, analysis, support_count=support_count)
    llm_result["score_delta"] = analysis["score_delta"]
    score_delta = score_analysis(analysis)
    weak = analysis.get("understanding_level") in {"weak", "wrong", "unclear"} or analysis.get("recommended_next_action") in {"reteach", "clarify"}
    topic_ref = update_topic_progress(
        payload.student_id,
        subject=subject,
        level=level,
        topic=topic,
        concept=concept,
        score_delta=score_delta,
        weak=weak,
    )
    mastery_cap = 85 if support_count >= 2 or status == "weak" else None
    topic_ref = _update_concept_status(
        payload.student_id,
        subject=subject,
        level=level,
        topic=topic,
        concept=concept,
        status=status,
        cap_mastery=mastery_cap,
    )

    session["last_analysis"] = analysis
    session["clarification_open"] = analysis.get("recommended_next_action") in {"reteach", "clarify"}
    base_should_advance = (
        analysis.get("recommended_next_action") in {"move_next", "start_activity"}
        and analysis.get("understanding_level") == "strong"
    )
    should_advance = False if _decision_blocks_advance(tutor_decision) else (base_should_advance or decision_advance)
    if tutor_decision.get("student_message_intent") == "wants_to_move_on":
        should_advance = True
        analysis["recommended_next_action"] = "move_next"
        session["skipped_question_ids"] = session.get("skipped_question_ids", []) + [question["question_id"]]
    if (
        not should_advance
        and tutor_decision
        and tutor_decision.get("should_repeat_question") is False
        and (
            _followup_repeats_recent(feedback, recent_questions)
            or _followup_repeats_active_question(feedback, question)
        )
    ):
        if decision_advance:
            should_advance = True
        else:
            english_question, tamil_question = _non_repeated_followup(question, recent_questions)
            feedback = _replace_question_block(feedback, english_question, tamil_question)
            llm_result["student_visible_reply"] = feedback
    next_q = choose_next_question(
        subject,
        level,
        topic,
        "learning",
        session.get("asked_question_ids", []),
        question,
        analysis,
    ) if should_advance else None

    if not should_advance:
        _append_learning_turn(
            payload.student_id,
            session=session,
            question=question,
            student_message=payload.message,
            analysis=analysis,
            tutor_reply=feedback,
        )
        save_current_session(payload.student_id, session)
        return {
            "ok": True,
            "message": feedback,
            "done": False,
            "session": session,
            "progress": topic_ref,
            "analysis": analysis,
            "llm_result": llm_result,
        }

    if next_q is None:
        session["topic_status"] = "completed"
        msg = _replace_question_block(
            feedback,
            f"You've completed this topic for now. Mastery: {topic_ref.get('topic_mastery', 0)}%.",
            f"இந்தப் பாடத்தை இப்போது முடித்துள்ளீர்கள். தேர்ச்சி நிலை: {topic_ref.get('topic_mastery', 0)}%.",
        ) if _split_bilingual_message(feedback) else _bilingual_message(
            f"You've completed this topic for now. Mastery: {topic_ref.get('topic_mastery', 0)}%.",
            f"இந்தப் பாடத்தை இப்போது முடித்துள்ளீர்கள். தேர்ச்சி நிலை: {topic_ref.get('topic_mastery', 0)}%.",
            "Would you like another question later?",
            "பிறகு இன்னொரு கேள்வியை முயற்சிக்க விரும்புகிறீர்களா?",
        )
        _append_learning_turn(
            payload.student_id,
            session=session,
            question=question,
            student_message=payload.message,
            analysis=analysis,
            tutor_reply=msg,
        )
        save_current_session(payload.student_id, session)
        return {
            "ok": True,
            "message": msg,
            "done": True,
            "session": session,
            "progress": topic_ref,
        }

    if should_advance:
        session["current_question_id"] = next_q["question_id"]
        session["current_concept"] = next_q.get("concept", "general")
        session["asked_question_ids"] = session.get("asked_question_ids", []) + [next_q["question_id"]]
        save_current_session(payload.student_id, session)
        english_question, tamil_question = await _display_question_pair(subject, level, topic, next_q)
        msg = _replace_question_block(
            feedback,
            english_question,
            tamil_question,
        ) if _split_bilingual_message(feedback) else _bilingual_message(
            "Let's try the next question.",
            "அடுத்த கேள்வியை முயற்சிப்போம்.",
            english_question,
            tamil_question,
        )
    else:
        save_current_session(payload.student_id, session)
        msg = feedback

    _append_learning_turn(
        payload.student_id,
        session=session,
        question=question,
        student_message=payload.message,
        analysis=analysis,
        tutor_reply=msg,
    )
    return {
        "ok": True,
        "message": msg,
        "done": False,
        "session": session,
        "progress": topic_ref,
        "analysis": analysis,
        "llm_result": llm_result,
    }
