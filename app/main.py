from __future__ import annotations
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException
import asyncio
import re
import logging
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import ADMIN_ENABLED, FRONTEND_DIR, KNOWLEDGEBASE_DIR
from .models import StartSessionRequest, ChatRequest, ExplainRequest
from .ingest import rebuild_all_indexes
from .retriever import topic_has_index, retrieve_context_text
from .session_manager import start_session, update_session
from .student_tracker import (
    ensure_student,
    get_current_session,
    save_current_session,
    append_exam_history,
    increment_clarification,
    snapshot_student,
    now_iso,
)
from .teaching_engine import choose_first_question, choose_next_question, score_exam_turn, clarify_with_context, translate_question_to_tamil
from .learning_flow import handle_learning_message
from .question_bank import find_question_by_id
from .guardrail_repair import _format_options_question
from scripts.convert_sources_to_knowledgebase import convert_sources, get_source_status


MODE_TAMIL_MAP = {
    "learning": "கற்றல்",
    "exam": "தேர்வு",
}


TOPIC_TAMIL_MAP = {
    "microorganisms": "நுண்ணுயிரிகள்",
    "03_microorganisms": "நுண்ணுயிரிகள்",
    "relationships_among_living_things": "உயிரினங்களுக்கு இடையிலான தொடர்புகள்",
    "04_relationships_among_living_things": "உயிரினங்களுக்கு இடையிலான தொடர்புகள்",
    "food_preservation": "உணவு பாதுகாப்பு",
    "08_food_preservation": "உணவு பாதுகாப்பு",
}


GENERIC_TAMIL_QUESTION = "மேலுள்ள கேள்விக்கு சுருக்கமாக பதில் சொல்ல முடியுமா?"


def _safe_path_part(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned or cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
        raise HTTPException(status_code=400, detail="Invalid subject or level.")
    return cleaned


def _topic_label(topic: str) -> str:
    label = re.sub(r"^\d+_", "", str(topic).strip())
    return label.replace("_", " ").title()


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


def _tamil_topic_name(topic: str) -> str:
    return TOPIC_TAMIL_MAP.get(str(topic).strip().lower(), str(topic).replace("_", " "))


def _english_topic_name(topic: str) -> str:
    label = re.sub(r"^\d+_", "", str(topic).strip().lower())
    return label.replace("_", " ")


def _tamil_mode_name(mode: str) -> str:
    return MODE_TAMIL_MAP.get(str(mode).strip().lower(), str(mode))


def _split_bilingual_message(text: str) -> tuple[str, str, str, str] | None:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if len(lines) < 4:
        return None
    return lines[0], lines[1], lines[2], lines[3]


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


def _normalize_message(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _detect_conversational_intent(message: str) -> str | None:
    msg = _normalize_message(message)
    if not msg:
        return None

    greetings = {"hi", "hello", "hey", "hello?", "hello??", "hey?", "hi?"}
    presence_checks = {
        "are you there",
        "are you there?",
        "u there",
        "u there?",
        "you there",
        "you there?",
        "hello??",
    }
    small_talk = {
        "how are you",
        "how are you?",
        "how r you",
        "how r you?",
        "what's up",
        "whats up",
        "what's up?",
        "whats up?",
    }
    off_topic = {
    }

    if msg in presence_checks:
        return "presence_check"
    if msg in greetings:
        return "greeting"
    if msg in small_talk:
        return "small_talk"
    if msg in off_topic:
        return "off_topic"
    return None


def _conversational_reply(intent: str) -> str:
    replies = {
        "greeting": _bilingual_message(
            "Hi! I'm here to help you learn.",
            "வணக்கம்! நான் உங்களுக்கு கற்றுக்கொள்ள உதவ இருக்கிறேன்.",
            "Ready to try the question?",
            "கேள்வியை முயற்சிக்க தயாரா?",
        ),
        "presence_check": _bilingual_message(
            "Yes, I'm here. Ready when you are.",
            "ஆம், நான் இங்கே இருக்கிறேன். நீங்கள் தயாரானவுடன் தொடங்கலாம்.",
            "Want to try the question?",
            "கேள்வியை முயற்சிக்க வேண்டுமா?",
        ),
        "small_talk": _bilingual_message(
            "I'm doing well and ready to help.",
            "நான் நன்றாக இருக்கிறேன், உதவ தயாராக இருக்கிறேன்.",
            "Want to get back to the question?",
            "மீண்டும் கேள்விக்குத் திரும்பலாமா?",
        ),
        "off_topic": _bilingual_message(
            "Let's stay on this question for now.",
            "இப்போதைக்கு இந்தக் கேள்வியிலேயே இருப்போம்.",
            "What do you think?",
            "நீங்கள் என்ன நினைக்கிறீர்கள்?",
        ),
    }
    return replies[intent]


app = FastAPI(title="AI EXZAM MVP")

@app.get("/api/status")
async def api_status():
    from .config import AI_PROVIDER
    return {
        "provider": AI_PROVIDER,
        "mode": "demo" if AI_PROVIDER == "mock" else "ai",
        "version": "tutor-v2",
        "admin_enabled": ADMIN_ENABLED,
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-store"})

@app.get("/app.js")
async def app_js() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "app.js", headers={"Cache-Control": "no-store"})

@app.get("/style.css")
async def style_css() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "style.css", headers={"Cache-Control": "no-store"})

@app.post("/api/admin/rebuild-index")
async def admin_rebuild_index():
    if not ADMIN_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    data = rebuild_all_indexes()
    return {
        "ok": True,
        "message": _bilingual_message(
            "Indexes are rebuilt.",
            "குறியீட்டு பட்டியல்கள் மீண்டும் உருவாக்கப்பட்டன.",
            "What would you like to do next?",
            "அடுத்து என்ன செய்ய விரும்புகிறீர்கள்?",
        ),
        "data": data,
    }

@app.post("/api/knowledge/generate")
async def api_generate_knowledgebase():
    if not ADMIN_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        summary = await asyncio.to_thread(convert_sources)
    except Exception as exc:
        return {
            "ok": False,
            "message": "Knowledgebase generation failed.",
            "data": {
                "errors": [f"{type(exc).__name__}: {exc}"],
                "next_step": "Fix the source conversion error, then try Generate Knowledgebase again.",
            },
        }
    return {
        "ok": True,
        "message": "Knowledgebase generation completed. Please click Rebuild Index before starting a session.",
        "data": summary,
    }

@app.get("/api/knowledge/source-status")
async def api_knowledge_source_status():
    if not ADMIN_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        return {"ok": True, "data": get_source_status()}
    except Exception as exc:
        return {
            "ok": False,
            "message": "Knowledge source status check failed.",
            "data": {"errors": [f"{type(exc).__name__}: {exc}"]},
        }

@app.get("/api/knowledge/topics")
async def api_knowledge_topics(subject: str = "science", level: str = "year6"):
    safe_subject = _safe_path_part(subject)
    safe_level = _safe_path_part(level)
    level_dir = KNOWLEDGEBASE_DIR / safe_subject / safe_level
    topics: list[dict[str, Any]] = []
    if level_dir.exists():
        for topic_dir in sorted([path for path in level_dir.iterdir() if path.is_dir()], key=lambda path: path.name):
            topics.append({
                "id": topic_dir.name,
                "label": _topic_label(topic_dir.name),
                "has_questions": any(topic_dir.rglob("*.xlsx")),
            })
    return {
        "ok": True,
        "data": {
            "subject": safe_subject,
            "level": safe_level,
            "topics": topics,
        },
    }

@app.post("/api/session/start")
async def api_start_session(payload: StartSessionRequest):
    ensure_student(payload.student_id, payload.student_name)

    if not topic_has_index(payload.subject, payload.level, payload.topic):
        rebuild_all_indexes()

    session = start_session(
        student_id=payload.student_id,
        student_name=payload.student_name,
        subject=payload.subject,
        level=payload.level,
        topic=payload.topic,
        mode=payload.mode,
    )

    first_q = choose_first_question(payload.subject, payload.level, payload.topic, payload.mode)
    if not first_q:
        raise HTTPException(status_code=404, detail="No questions found for this topic and mode.")

    session["current_question_id"] = first_q["question_id"]
    session["current_concept"] = first_q.get("concept", "general")
    session["asked_question_ids"] = [first_q["question_id"]]
    save_current_session(payload.student_id, session)

    english_question, tamil_question = await _display_question_pair(payload.subject, payload.level, payload.topic, first_q)
    opening = _bilingual_message(
        f"Let's begin {_english_topic_name(payload.topic)} in {payload.mode} mode.",
        f"{_tamil_topic_name(payload.topic)} பாடத்தை {_tamil_mode_name(payload.mode)} முறையில் தொடங்கலாம்.",
        english_question,
        tamil_question,
    )
    return {"ok": True, "message": opening, "session": session, "question": first_q}

@app.post("/api/chat/message")
async def api_chat_message(payload: ChatRequest):
    session = get_current_session(payload.student_id)
    if not session:
        raise HTTPException(status_code=400, detail="No active session. Start a session first.")
    if session.get("topic_status") in {"completed", "exam_completed"}:
        raise HTTPException(status_code=400, detail="This session is complete. Start a new session to continue.")

    subject = session["subject"]
    level = session["level"]
    topic = session["topic"]
    mode = payload.mode or session["mode"]

    current_question_id = session.get("current_question_id")
    if not current_question_id:
        raise HTTPException(status_code=400, detail="No current question in session.")

    question = find_question_by_id(subject, level, topic, current_question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Current question not found.")

    conversational_intent = _detect_conversational_intent(payload.message)
    if conversational_intent and mode != "exam":
        llm_result = {
            "student_visible_reply": _conversational_reply(conversational_intent),
            "intent": conversational_intent,
            "understanding_level": "unclear",
            "missing_concepts": [],
            "misconception_tags": [],
            "recommended_next_action": "clarify",
            "score_delta": 0,
        }
        analysis = {
            "intent": conversational_intent,
            "understanding_level": "unclear",
            "missing_concepts": [],
            "misconception_tags": [],
            "recommended_next_action": "clarify",
            "score_delta": 0,
            "concept": question.get("concept") or session.get("current_concept") or "general",
        }
        return {
            "ok": True,
            "message": llm_result["student_visible_reply"],
            "done": False,
            "session": session,
            "analysis": analysis,
            "llm_result": llm_result,
        }

    if mode == "exam":
        evaluation = await score_exam_turn(
            student_id=payload.student_id,
            subject=subject,
            level=level,
            topic=topic,
            question=question,
            student_answer=payload.message,
        )
        score = int(evaluation.get("score_awarded", 0))

        exam_answers = session.get("exam_answers", [])
        exam_answers.append({
            "timestamp": now_iso(),
            "question_id": question["question_id"],
            "question_text": question["question_text"],
            "student_answer": payload.message,
            "score": score,
            "max_marks": question.get("marks", 1),
            "evaluation": evaluation,
        })
        session["exam_answers"] = exam_answers

        next_q = choose_next_question(subject, level, topic, "exam", session.get("asked_question_ids", []), question, None)
        if next_q is None:
            total = sum(x["score"] for x in exam_answers)
            maximum = sum(x["max_marks"] for x in exam_answers)
            percent = round((total / maximum) * 100) if maximum else 0
            append_exam_history(payload.student_id, {
                "timestamp": now_iso(),
                "subject": subject,
                "level": level,
                "topic": topic,
                "answers": exam_answers,
                "score": total,
                "max_score": maximum,
                "percent": percent,
            })
            session["topic_status"] = "exam_completed"
            save_current_session(payload.student_id, session)
            return {
                "ok": True,
                "message": _bilingual_message(
                    f"Exam finished. Your score is {total}/{maximum} ({percent}%).",
                    f"தேர்வு முடிந்தது. உங்கள் மதிப்பெண் {total}/{maximum} ({percent}%).",
                    "Would you like to review another topic?",
                    "வேறு ஒரு பாடத்தை மீண்டும் பார்க்க வேண்டுமா?",
                ),
                "done": True,
                "session": session,
            }

        session["current_question_id"] = next_q["question_id"]
        session["current_concept"] = next_q.get("concept", "general")
        session["asked_question_ids"] = session.get("asked_question_ids", []) + [next_q["question_id"]]
        save_current_session(payload.student_id, session)
        english_question, tamil_question = await _display_question_pair(subject, level, topic, next_q)
        return {
            "ok": True,
            "message": _replace_question_block(
                evaluation.get("student_visible_reply", ""),
                english_question,
                tamil_question,
            ) if _split_bilingual_message(evaluation.get("student_visible_reply", "")) else _bilingual_message(
                "Answer recorded.",
                "உங்கள் பதில் பதிவு செய்யப்பட்டது.",
                english_question,
                tamil_question,
            ),
            "done": False,
            "session": session,
            "question": next_q,
        }

    try:
        return await handle_learning_message(payload, session, question)
    except RuntimeError as exc:
        cause = exc
        chain = []
        while cause is not None:
            chain.append(type(cause).__name__)
            cause = cause.__cause__
        logging.getLogger(__name__).error("Tutor unavailable: %s", " -> ".join(chain))
        raise HTTPException(status_code=503, detail="The AI tutor is temporarily unavailable. Your answer has not been graded. Please retry.") from exc

@app.post("/api/chat/clarify")
@app.post("/api/chat/explain")
async def api_chat_clarify(payload: ExplainRequest):
    session = get_current_session(payload.student_id)
    if not session:
        raise HTTPException(status_code=400, detail="No active session.")

    subject = session["subject"]
    level = session["level"]
    topic = session["topic"]

    increment_clarification(payload.student_id, subject, level, topic)
    text = await clarify_with_context(subject, level, topic, payload.ask)
    return {"ok": True, "message": text}

@app.get("/api/student/{student_id}/snapshot")
async def api_student_snapshot(student_id: str):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", student_id):
        raise HTTPException(status_code=400, detail="Invalid student ID.")
    return {"ok": True, "data": snapshot_student(student_id)}

@app.get("/api/topic/context")
async def api_topic_context(subject: str, level: str, topic: str, query: str):
    return {
        "ok": True,
        "message": "Context retrieved.",
        "data": {
            "context": retrieve_context_text(subject, level, topic, query),
        },
    }
