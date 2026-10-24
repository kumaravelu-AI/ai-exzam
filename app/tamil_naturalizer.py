from __future__ import annotations
from typing import Any, Awaitable, Callable, Optional
import json
import os
import re

from .config import TAMIL_NATURALIZER_ENABLED
from .response_formatter import _bilingual_message, _split_bilingual_message


ChatTextFn = Callable[[str, str], Awaitable[str]]
AI_DEBUG = os.getenv("AI_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
TAMIL_NATURALIZER_FAST_MODE = os.getenv("TAMIL_NATURALIZER_FAST_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}


def _strip_json_fence(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _has_tamil(text: str) -> bool:
    return any("\u0b80" <= ch <= "\u0bff" for ch in (text or ""))


def _clean_one_line(text: str) -> str:
    cleaned = re.sub(r"[\r\n]+", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _clean_topic_tamil_terms(
    *,
    english_response: str,
    english_followup: str,
    tamil_response: str,
    tamil_followup: str,
) -> tuple[str, str]:
    response = tamil_response or ""
    followup = tamil_followup or ""
    followup = followup.replace("யாதெனில்", "சொல்ல முடியுமா")
    response = response.replace("உரியது!", "சரி.")
    response = response.replace("உரியது.", "சரி.")
    response = response.replace("உண்மையில்!", "சரி.")
    response = response.replace("உண்மையில்.", "சரி.")
    response = response.replace("உங்கள் கூற்று உண்மையானது!", "சரி.")
    response = response.replace("உங்கள் கூற்று உண்மையானது.", "சரி.")
    response = response.replace("உங்கள் கூற்று சரியானது!", "சரி!")
    response = response.replace("உங்கள் கூற்று சரியானது.", "சரி.")
    response = response.replace("உங்கள் கூற்று சரியாகும்!", "சரி.")
    response = response.replace("உங்கள் கூற்று சரியாகும்.", "சரி.")
    response = response.replace("உங்கள் கருத்து உரியது", "நீங்கள் சொல்வது சரி")
    response = response.replace("சரியாக!", "சரி.")
    response = response.replace("இது ஒரு சிறந்த தொடக்கம்!", "நல்ல தொடக்கம்!")
    response = response.replace("இது ஒரு சிறந்த தொடக்கம்.", "நல்ல தொடக்கம்.")
    response = response.replace(
        "உணவு பாதுகாப்பு கெட்டுப்போவதை தடுக்கிறது அல்லது நுண்ணுயிர் வளர்ச்சியை தடுக்கிறது",
        "உணவு கெடாமல் இருக்கவும், நுண்ணுயிர் வளர்ச்சியை குறைக்கவும் உணவு பாதுகாப்பு உதவுகிறது",
    )
    response = response.replace("இது உணவு நீண்ட நாட்கள் இருக்க உதவுகிறது", "இது உணவு நீண்ட நாட்கள் கெடாமல் இருக்க உதவுகிறது")
    response = response.replace("உணவை நீண்ட நாட்கள் இருக்க அல்லது கெட்டுப்போவதை தடுக்க", "உணவு நீண்ட நாட்கள் கெடாமல் இருக்க")
    response = response.replace("உணவை நீண்ட நாட்கள் இருக்க", "உணவு நீண்ட நாட்கள் கெடாமல் இருக்க")
    response = response.replace("வாழ உதவுகிறது", "இருக்க உதவுகிறது")
    response = response.replace("கவனித்துக் கொள்ளவில்லை", "சேர்க்கவில்லை")
    response = response.replace("அவை மட்டும் நம் கண்களால்", "அவை நம் கண்களால் மட்டும்")
    response = response.replace("அவை மட்டும் நமது கண்களால்", "அவை நமது கண்களால் மட்டும்")
    followup = followup.replace("எங்கள் உணவை பாதுகாப்பதற்கான ஏன்?", "நாம் உணவை ஏன் பாதுகாக்கிறோம்?")
    followup = followup.replace("நாம் உணவை பாதுகாப்பதற்கான ஏன்?", "நாம் உணவை ஏன் பாதுகாக்கிறோம்?")
    followup = followup.replace("பாதுகாப்பதற்கான ஏன்?", "ஏன் பாதுகாக்கிறோம்?")
    followup = followup.replace("நாம் உணவை பாதுகாக்க காரணம் ஏன்?", "நாம் உணவை ஏன் பாதுகாக்கிறோம்?")
    followup = followup.replace("காரணம் ஏன்?", "ஏன்?")
    followup = followup.replace("எதிர்பார்க்கிறாயா", "சொல்ல முடியுமா")
    followup = followup.replace("எதிர்பார்க்கிறீர்களா", "சொல்ல முடியுமா")
    return response, followup


def _neutral_tamil_followup(english_followup: str) -> str:
    return ""


def _normalized_english(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _preferred_followup_translation(english_followup: str) -> str:
    lookup = {
        "what are microorganisms": "நுண்ணுயிரிகள் என்றால் என்ன?",
        "is bacteria a microorganism": "பாக்டீரியா ஒரு நுண்ணுயிரியா?",
        "why do living things interact with each other": "உயிரினங்கள் ஏன் ஒன்றுடன் ஒன்று தொடர்பு கொள்கின்றன?",
        "what is prey": "இரை என்றால் என்ன?",
        "why do we preserve food": "நாம் உணவை ஏன் பாதுகாக்கிறோம்?",
        "which microorganism helps bread rise": "ரொட்டி உயர எந்த நுண்ணுயிரி உதவுகிறது?",
        "what is food preservation": "உணவு பாதுகாப்பு என்றால் என்ன?",
    }
    return lookup.get(_normalized_english(english_followup), "")


async def _chat_json(chat_text: ChatTextFn, system: str, user: str) -> dict[str, Any]:
    text = await chat_text(system, user)
    try:
        return json.loads(_strip_json_fence(text))
    except json.JSONDecodeError:
        repair_prompt = f"""
Repair this output into valid JSON only.
Keep exactly these keys:
tamil_response
tamil_followup

Broken output:
{text}
"""
        repaired = await chat_text(
            "You repair malformed JSON. Return valid JSON only.",
            repair_prompt,
        )
        return json.loads(_strip_json_fence(repaired))


def _has_obvious_meaning_reversal(
    english_response: str,
    english_followup: str,
    tamil_response: str,
    tamil_followup: str,
) -> bool:
    if _question_type_mismatch(english_followup, tamil_followup):
        return True
    if "why" in english_followup.lower() and "எப்படி" in tamil_followup:
        return True

    return False


def _question_type_mismatch(english_followup: str, tamil_followup: str) -> bool:
    english = re.sub(r"\s+", " ", (english_followup or "").strip().lower())
    tamil = re.sub(r"\s+", " ", tamil_followup or "").strip()
    if not english or not tamil:
        return False
    if english.startswith("why") and not any(token in tamil for token in ("ஏன்", "எதற்காக", "காரணம்")):
        return True
    if english.startswith("how") and not any(token in tamil for token in ("எப்படி", "எவ்வாறு")):
        return True
    if english.startswith("which") and not any(token in tamil for token in ("எது", "எந்த")):
        return True
    if english.startswith("what") and not any(token in tamil for token in ("என்ன", "என்றால்")):
        return True
    return False


def _english_specific_terms(text: str) -> set[str]:
    stop_words = {
        "the", "and", "are", "you", "your", "this", "that", "what", "why", "how",
        "can", "could", "would", "one", "some", "with", "from", "about", "answer",
        "question", "tell", "name", "give", "try", "which", "does", "do",
    }
    return {
        word
        for word in re.findall(r"[a-zA-Z]+", (text or "").lower())
        if len(word) > 3 and word not in stop_words
    }


def _is_generic_tamil_question(tamil_followup: str, english_followup: str) -> bool:
    tamil = re.sub(r"\s+", " ", tamil_followup or "").strip()
    generic_questions = {
        "இந்தக் கேள்விக்கு பதில் சொல்ல முடியுமா?",
        "மேலுள்ள கேள்விக்கு சுருக்கமாக பதில் சொல்ல முடியுமா?",
        "இப்போது ஒரு சுருக்கமான பதிலை சொல்ல முடியுமா?",
        "இப்போது நீங்கள் என்ன நினைக்கிறீர்கள்?",
        "அதை சொல்ல முடியுமா?",
    }
    return tamil in generic_questions and len(_english_specific_terms(english_followup)) >= 2


def _has_bad_tamil_pattern(tamil_response: str, tamil_followup: str) -> bool:
    tamil = f"{tamil_response} {tamil_followup}"
    bad_patterns = (
        "இந்த கருத்தை எளிதாக நினைவில் கொள்ளுங்கள்",
        "இதைக் கொஞ்சம் தெளிவாகப் பார்ப்போம்",
        "மேலுள்ள கேள்விக்கு சுருக்கமாக பதில் சொல்ல முடியுமா",
        "மைக்ரோஆர்க்கனிசம்",
        "மைக்ரோஆர்க்கனிசங்கள்",
        "வாழ்வியல் உயிரினங்கள்",
        "வாழும் பொருட்கள்",
        "புலன் கண்கள்",
        "புலப்படாத",
        "வாழ்த்தலாம்",
        "வாழ உதவுகிறது",
        "நீ குறிப்பிட்டாலும்",
        "நீ கவனித்துக் கொள்ளவில்லை",
        "கவனித்துக் கொள்ளவில்லை",
        "எதிர்பார்க்கிறாயா",
        "எதிர்பார்க்கிறீர்களா",
        "உணவை நீண்ட நாட்கள் இருக்க",
        "இது ஒரு சிறந்த தொடக்கம்",
        "காரணம் ஏன்",
        "பாதுகாப்பதற்கான ஏன்",
        "உண்மையில்!",
        "உங்கள் கூற்று சரியாகும்",
        "உரியது",
        "நீங்கள் கூறியதாவது",
        "உங்களுக்கு எண்ணம் வருகிறது",
        "உங்கள் கருத்தில் எடுத்துக்கொள்ளுங்களா",
        "உங்கள் கவனத்தில் கொள்ளுங்களா",
        "முந்தைய கேள்விக்கு திரும்புங்கள்",
    )
    return any(pattern in tamil for pattern in bad_patterns)


async def _meaning_checked_tamil_fields(
    *,
    english_response: str,
    english_followup: str,
    tamil_response: str,
    tamil_followup: str,
    chat_text: ChatTextFn,
    reference_context: str = "",
) -> Optional[tuple[str, str]]:
    system = (
        "You are a bilingual Tamil science meaning checker and Tamil rewrite editor. "
        "Check a Tamil candidate that was generated from English. "
        "Always use the English source as the only meaning authority. "
        "If the Tamil reverses, weakens, or changes the meaning, rewrite it from English. "
        "Use natural school-level Tamil. Return valid JSON only."
    )
    user = f"""
Return JSON with exactly these keys:
meaning_ok
tamil_response
tamil_followup

    Rules:
- meaning_ok must be true only if Tamil matches English.
- If meaning_ok is false, provide corrected Tamil fields.
- Do not change the English meaning.
- Do not add extra teaching content.
- Keep Tamil short and natural for Tamil primary school students.
- Use a warm teacher tone. Avoid blaming phrases that sound like "you failed to notice".
- Use நீங்கள் or neutral classroom Tamil; avoid rough spoken forms such as நீ குறிப்பிட்டாலும்.
- If the reference context contains glossary/key-term pairs such as "English = Tamil", use those Tamil terms exactly when that English term appears.
- Preserve list relationships exactly; do not turn two examples of one category into one example being a type of the other.
- Preserve the question target exactly; if English asks for a type/example of one concept, Tamil must ask about that same concept.
- If English says "X and Y are types/examples of Z", Tamil must keep X and Y as separate examples of Z.
- If English says "besides X and Y", Tamil must ask for something other than X and Y, not a type of X or Y.
- Do not repeat a noun in Tamil unless the English repeats that noun.
- Prefer these classroom Tamil terms when relevant: நுண்ணுயிரிகள், நுண்ணோக்கி, பாக்டீரியா, வைரஸ், ஈஸ்ட், பூஞ்சை, தயிர், ரொட்டி உயர உதவுகிறது, வேட்டையாடி, இரை, போட்டி, உணவு பாதுகாப்பு, உணவு கெடுதல், உலர்த்துதல், உறையவைத்தல்.
- Avoid: மைக்ரோஆர்க்கனிசம், மைக்ரோஆர்க்கனிசங்கள், உரியது, நீங்கள் கூறியதாவது, உங்களுக்கு எண்ணம் வருகிறது, புலன் கண்கள், வாழ்வியல் உயிரினங்கள்.

English response:
{english_response}

English follow-up:
{english_followup}

Tamil response:
{tamil_response}

Tamil follow-up:
{tamil_followup}

Reference context for glossary only:
{reference_context[:1200]}
"""
    checked = await _chat_json(chat_text, system, user)
    checked_response = _clean_one_line(str(checked.get("tamil_response") or ""))
    checked_followup = _clean_one_line(str(checked.get("tamil_followup") or ""))
    if not _has_tamil(checked_response) or not _has_tamil(checked_followup):
        return None
    if _has_obvious_meaning_reversal(
        english_response,
        english_followup,
        checked_response,
        checked_followup,
    ):
        return None
    return checked_response, checked_followup


async def _strict_tamil_rewrite(
    *,
    english_response: str,
    english_followup: str,
    chat_text: ChatTextFn,
    reference_context: str = "",
) -> Optional[tuple[str, str]]:
    system = (
        "You are a Tamil primary-school teacher. "
        "Write Tamil only from the English source meaning. "
        "Do not use or infer from any rough Tamil. "
        "Do not copy generic placeholder questions. "
        "Never answer with a vague phrase like 'answer the above question' when the English has a specific question. "
        "Return valid JSON only."
    )
    user = f"""
Return JSON with exactly these keys:
tamil_response
tamil_followup

Rules:
- Translate meaning, not word-by-word.
- tamil_response must match english_response.
- tamil_followup must match english_followup and keep the same question type.
- Do not use generic placeholder questions when English has a specific question.
- If the English asks a definition question, the Tamil must ask the same definition question.
- If the English asks an easy check question, the Tamil must ask that exact easy check question meaning.
- Do not change examples, positives, negatives, or named concepts.
- Keep Tamil short, natural, and suitable for primary school.
- Use glossary terms from reference context when available.
- Prefer these classroom Tamil terms when relevant: நுண்ணுயிரிகள், நுண்ணோக்கி, பாக்டீரியா, வைரஸ், ஈஸ்ட், பூஞ்சை, தயிர், ரொட்டி உயர உதவுகிறது, வேட்டையாடி, இரை, போட்டி, உணவு பாதுகாப்பு, உணவு கெடுதல், உலர்த்துதல், உறையவைத்தல்.
- Avoid: மைக்ரோஆர்க்கனிசம், மைக்ரோஆர்க்கனிசங்கள், உரியது, நீங்கள் கூறியதாவது, உங்களுக்கு எண்ணம் வருகிறது, புலன் கண்கள், வாழ்வியல் உயிரினங்கள்.
- Use a warm teacher tone. Avoid blaming phrases that sound like "you failed to notice".
- Use நீங்கள் or neutral classroom Tamil; avoid rough spoken forms such as நீ குறிப்பிட்டாலும்.
- For non-living things, do not use வாழ to mean "last longer"; use natural wording such as நீண்ட நாட்கள் இருக்க or கெடாமல் இருக்க.
- Prefer உயிரினங்கள் for living things; do not use வாழும் பொருட்கள்.
- Prefer தெளிவாக பார்க்க முடியாத for too small to see clearly; avoid overly formal wording like புலப்படாத.

English response:
{english_response}

English follow-up:
{english_followup}

Reference context:
{reference_context[:1200]}
"""
    rewritten = await _chat_json(chat_text, system, user)
    tamil_response = _clean_one_line(str(rewritten.get("tamil_response") or ""))
    tamil_followup = _clean_one_line(str(rewritten.get("tamil_followup") or ""))
    if not _has_tamil(tamil_response) or not _has_tamil(tamil_followup):
        return None
    if (
        _is_generic_tamil_question(tamil_followup, english_followup)
        or _has_bad_tamil_pattern(tamil_response, tamil_followup)
        or _question_type_mismatch(english_followup, tamil_followup)
    ):
        return None
    return tamil_response, tamil_followup


async def _safe_fallback_tamil_rewrite(
    *,
    english_response: str,
    english_followup: str,
    chat_text: ChatTextFn,
    reference_context: str = "",
) -> Optional[tuple[str, str]]:
    system = (
        "You convert English tutor text into simple natural Tamil for SJKT primary science students. "
        "Use only the English meaning. Do not add content. Do not use rough Tamil. "
        "Return valid JSON only."
    )
    user = f"""
Return JSON with exactly these keys:
tamil_response
tamil_followup

Rules:
- tamil_response must express only english_response.
- tamil_followup must express only english_followup.
- Keep the same examples, names, positive/negative meaning, and question type.
- Do not replace a specific question with a generic question.
- Use short, natural Tamil suitable for Standard 6/SJKT science.
- Prefer: நுண்ணுயிரிகள், நுண்ணோக்கி, பாக்டீரியா, வைரஸ், ஈஸ்ட், பூஞ்சை, தயிர், ரொட்டி உயர உதவுகிறது, வேட்டையாடி, இரை, போட்டி, உணவு பாதுகாப்பு, உணவு கெடுதல், உலர்த்துதல், உறையவைத்தல்.
- Avoid: மைக்ரோஆர்க்கனிசம், மைக்ரோஆர்க்கனிசங்கள், உரியது, நீங்கள் கூறியதாவது, உங்களுக்கு எண்ணம் வருகிறது, புலன் கண்கள், வாழ்வியல் உயிரினங்கள்.

English response:
{english_response}

English follow-up:
{english_followup}

Reference context for term choice only:
{reference_context[:1200]}
"""
    rewritten = await _chat_json(chat_text, system, user)
    tamil_response = _clean_one_line(str(rewritten.get("tamil_response") or ""))
    tamil_followup = _clean_one_line(str(rewritten.get("tamil_followup") or ""))
    tamil_response, tamil_followup = _clean_topic_tamil_terms(
        english_response=english_response,
        english_followup=english_followup,
        tamil_response=tamil_response,
        tamil_followup=tamil_followup,
    )
    preferred_followup = _preferred_followup_translation(english_followup)
    if preferred_followup:
        tamil_followup = preferred_followup
    if not _has_tamil(tamil_response) or not _has_tamil(tamil_followup):
        return None
    if (
        _is_generic_tamil_question(tamil_followup, english_followup)
        or _has_bad_tamil_pattern(tamil_response, tamil_followup)
        or _question_type_mismatch(english_followup, tamil_followup)
    ):
        return None
    return tamil_response, tamil_followup


def _debug_fallback_used(stage: str) -> None:
    if AI_DEBUG:
        print(f"AI_DEBUG tamil_naturalizer_fallback={stage}")


def _validated_tamil_pair(
    *,
    english_response: str,
    english_followup: str,
    tamil_response: str,
    tamil_followup: str,
) -> Optional[tuple[str, str]]:
    tamil_response = _clean_one_line(tamil_response)
    tamil_followup = _clean_one_line(tamil_followup)
    tamil_response, tamil_followup = _clean_topic_tamil_terms(
        english_response=english_response,
        english_followup=english_followup,
        tamil_response=tamil_response,
        tamil_followup=tamil_followup,
    )
    preferred_followup = _preferred_followup_translation(english_followup)
    if preferred_followup:
        tamil_followup = preferred_followup
    if not _has_tamil(tamil_response) or not _has_tamil(tamil_followup):
        return None
    if (
        _is_generic_tamil_question(tamil_followup, english_followup)
        or _has_bad_tamil_pattern(tamil_response, tamil_followup)
        or _question_type_mismatch(english_followup, tamil_followup)
        or _has_obvious_meaning_reversal(
            english_response,
            english_followup,
            tamil_response,
            tamil_followup,
        )
    ):
        return None
    return tamil_response, tamil_followup


async def naturalize_tamil_fields(data: dict[str, Any], chat_text: ChatTextFn) -> dict[str, Any]:
    """Optionally rewrite only Tamil fields; never changes tutor decisions or English."""
    return await naturalize_tamil_fields_with_context(data, chat_text, reference_context="")


async def naturalize_tamil_fields_with_context(
    data: dict[str, Any],
    chat_text: ChatTextFn,
    *,
    reference_context: str = "",
) -> dict[str, Any]:
    """Optionally rewrite only Tamil fields; never changes tutor decisions or English."""
    if not TAMIL_NATURALIZER_ENABLED:
        return data

    english_response = str(data.get("english_response") or "").strip()
    english_followup = str(data.get("english_followup") or "").strip()
    if not english_response or not english_followup:
        return data

    if TAMIL_NATURALIZER_FAST_MODE:
        tamil_response = str(data.get("tamil_response") or "").strip()
        tamil_followup = str(data.get("tamil_followup") or "").strip()
        candidate = _validated_tamil_pair(
            english_response=english_response,
            english_followup=english_followup,
            tamil_response=tamil_response,
            tamil_followup=tamil_followup,
        )
        if candidate is not None:
            updated = dict(data)
            updated["tamil_response"], updated["tamil_followup"] = candidate
            return updated
        _debug_fallback_used("fast_mode_strict_rewrite")

    candidate: Optional[tuple[str, str]] = None
    for attempt in range(2):
        try:
            strict = await _strict_tamil_rewrite(
                english_response=english_response,
                english_followup=english_followup,
                chat_text=chat_text,
                reference_context=reference_context,
            )
        except Exception:
            strict = None
        if strict is not None:
            candidate = _validated_tamil_pair(
                english_response=english_response,
                english_followup=english_followup,
                tamil_response=strict[0],
                tamil_followup=strict[1],
            )
        if candidate is not None:
            break
        if attempt == 0:
            _debug_fallback_used("strict_retry")

    if candidate is None:
        _debug_fallback_used("safe_fallback")
        try:
            fallback = await _safe_fallback_tamil_rewrite(
                english_response=english_response,
                english_followup=english_followup,
                chat_text=chat_text,
                reference_context=reference_context,
            )
        except Exception:
            fallback = None
        if fallback is not None:
            candidate = _validated_tamil_pair(
                english_response=english_response,
                english_followup=english_followup,
                tamil_response=fallback[0],
                tamil_followup=fallback[1],
            )

    if candidate is None:
        _debug_fallback_used("original_data_last_resort")
        return data

    tamil_response, tamil_followup = candidate

    updated = dict(data)
    updated["tamil_response"] = tamil_response
    updated["tamil_followup"] = tamil_followup
    return updated


async def naturalize_visible_reply(
    reply: str,
    chat_text: ChatTextFn,
    *,
    reference_context: str = "",
) -> str:
    """Optionally naturalize the final visible Tamil after all guardrail repairs."""
    if not TAMIL_NATURALIZER_ENABLED:
        return reply

    parts = _split_bilingual_message(reply)
    if not parts:
        return reply

    english_response, english_followup, tamil_response, tamil_followup = parts
    data = {
        "english_response": english_response,
        "english_followup": english_followup,
        "tamil_response": tamil_response,
        "tamil_followup": tamil_followup,
    }
    updated = await naturalize_tamil_fields_with_context(data, chat_text, reference_context=reference_context)
    tamil_followup_out = str(updated.get("tamil_followup") or tamil_followup)
    tamil_response_out = str(updated.get("tamil_response") or tamil_response)
    tamil_response_out, tamil_followup_out = _clean_topic_tamil_terms(
        english_response=english_response,
        english_followup=english_followup,
        tamil_response=tamil_response_out,
        tamil_followup=tamil_followup_out,
    )
    neutral_followup = _neutral_tamil_followup(english_followup)
    if neutral_followup:
        tamil_followup_out = neutral_followup
    return _bilingual_message(
        english_response,
        tamil_response_out,
        english_followup,
        tamil_followup_out,
    )
