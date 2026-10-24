from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT_DIR / "knowledge_sources"
KNOWLEDGEBASE_DIR = ROOT_DIR / "knowledgebase"
MANIFEST_PATH = SOURCE_DIR / "conversion_manifest.json"
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".xlsx"}


@dataclass(frozen=True)
class TopicSpec:
    key: str
    folder: str
    title: str
    keywords: tuple[str, ...]
    notes: tuple[str, ...]
    questions: tuple[str, ...]
    misconceptions: tuple[str, ...]
    key_terms: tuple[tuple[str, str, str], ...]


TOPICS: tuple[TopicSpec, ...] = (
    TopicSpec(
        key="microorganisms",
        folder="03_microorganisms",
        title="Microorganisms",
        keywords=(
            "microorganism", "microorganisms", "bacteria", "virus", "fungi",
            "fungus", "yeast", "algae", "protozoa", "microscope",
            "mikroorganisma", "நுண்ணுயிர",
        ),
        notes=(
            "Microorganisms are very tiny living things.",
            "They usually cannot be seen clearly with only our eyes.",
            "A microscope is used to see microorganisms clearly.",
            "Types include virus, bacteria, fungi, algae, protozoa, and yeast.",
            "Microorganisms breathe, move, and grow.",
            "Useful microorganisms help make bread, curd or yogurt, medicine, compost, and support wastewater treatment.",
            "Harmful microorganisms can spoil food, cause diseases, tooth decay, food poisoning, and infections.",
            "Microorganisms can spread through air, water, food, touch, and animals.",
            "Non-examples: birds, ants, rocks, air, and mango trees are not microorganisms.",
        ),
        questions=(
            "What are microorganisms?",
            "Why do we need a microscope to see microorganisms?",
            "Give two examples of microorganisms.",
            "Is bacteria a microorganism?",
            "Is a bird a microorganism? Why?",
            "True or false: All microorganisms are harmful.",
            "Which one is a microorganism: bacteria, tiger, rock, or mango tree?",
            "Why is air not a microorganism?",
            "Which microorganism helps bread rise?",
            "Give one example of a useful microorganism.",
        ),
        misconceptions=(
            "Wrong idea: all small things are microorganisms. Correction: a microorganism is a tiny living thing, not just any small object.",
            "Wrong idea: air is a microorganism. Correction: air is not a living thing.",
            "Wrong idea: all microorganisms are harmful. Correction: some are useful, such as yeast and good bacteria.",
            "Wrong idea: insects like ants are microorganisms. Correction: ants are visible animals, not microorganisms.",
            "Wrong idea: virus is not a microorganism. Correction: viruses are treated as microorganisms in this Year 6 topic.",
        ),
        key_terms=(
            ("Microorganisms", "நுண்ணுயிரிகள்", "Very tiny living things."),
            ("Bacteria", "பாக்டீரியா", "A type of microorganism."),
            ("Virus", "வைரஸ்", "A very tiny microorganism."),
            ("Fungi", "பூஞ்சை", "A group of microorganisms."),
            ("Yeast", "ஈஸ்ட்", "A useful fungus that helps bread rise."),
            ("Algae", "அலகி", "A type of microorganism that can live in water."),
            ("Protozoa", "புரோட்டோசோவா", "A type of microorganism."),
            ("Microscope", "நுண்ணோக்கி", "A tool used to see very tiny things clearly."),
            ("Useful", "பயனுள்ள", "Something that helps us."),
            ("Harmful", "தீங்கு விளைவிக்கும்", "Something that can cause harm."),
            ("Curd/Yogurt", "தயிர்", "Food made with help from good bacteria."),
            ("Bread rises", "ரொட்டி உயருகிறது", "Bread becomes bigger and soft with help from yeast."),
        ),
    ),
    TopicSpec(
        key="relationships_among_living_things",
        folder="04_relationships_among_living_things",
        title="Relationships Among Living Things",
        keywords=(
            "relationship", "relationships", "living things", "interaction",
            "interactions", "competition", "symbiosis", "predator", "prey",
            "food chain", "habitat", "interaksi", "persaingan", "simbiosis",
        ),
        notes=(
            "Living things interact with one another to get food, water, shelter, space, and protection.",
            "Competition happens when living things need the same limited resources.",
            "Predator-prey relationships happen when one animal hunts another animal for food.",
            "Some relationships help both living things, while some help one living thing and may harm another.",
            "Plants and animals depend on each other in habitats and food chains.",
            "Generated learning support: use local examples such as birds, insects, plants, and animals when explaining relationships.",
        ),
        questions=(
            "Why do living things interact with each other?",
            "What is competition among living things?",
            "Give one example of animals competing for food.",
            "What is a predator?",
            "What is prey?",
            "True or false: Living things never depend on each other.",
            "Which is an example of a relationship: a bird eating a worm, a rock on a table, or a pencil in a bag?",
            "Why do plants compete for sunlight?",
        ),
        misconceptions=(
            "Wrong idea: only animals interact. Correction: plants also interact and compete for resources.",
            "Wrong idea: competition means fighting only. Correction: it means living things need the same limited resource.",
            "Wrong idea: predator and prey are friends. Correction: predator hunts prey for food.",
            "Wrong idea: non-living things have relationships like living things. Correction: this topic focuses on living things.",
        ),
        key_terms=(
            ("Living things", "உயிரினங்கள்", "Things that can grow, need food or water, and reproduce."),
            ("Relationship", "தொடர்பு", "How living things affect or depend on each other."),
            ("Interaction", "இடையினைவு", "Action between living things."),
            ("Competition", "போட்டி", "When living things need the same limited resource."),
            ("Predator", "வேட்டையாடி", "An animal that hunts another animal for food."),
            ("Prey", "இரை", "An animal that is hunted for food."),
            ("Habitat", "வாழிடம்", "The place where a living thing lives."),
            ("Food chain", "உணவுச் சங்கிலி", "A chain showing how living things get food energy."),
        ),
    ),
    TopicSpec(
        key="food_preservation",
        folder="08_food_preservation",
        title="Food Preservation",
        keywords=(
            "food preservation", "preserve food", "preservation", "food spoilage",
            "spoil", "spoiled", "drying", "boiling", "cooling", "freezing",
            "salting", "pickling", "smoking", "canning", "vacuum", "pasteur",
            "pengawetan", "makanan",
        ),
        notes=(
            "Food preservation helps food last longer and reduces food spoilage.",
            "Food can spoil because microorganisms grow on it.",
            "Preservation methods slow down or stop the growth of microorganisms.",
            "Common methods include drying, boiling, cooling, freezing, salting, pickling, smoking, canning, vacuum packing, and pasteurisation.",
            "Different foods need different preservation methods.",
            "Generated learning support: connect food preservation to daily examples such as dried fish, jam, pickles, milk, and frozen food.",
        ),
        questions=(
            "What is food preservation?",
            "Why do we preserve food?",
            "How can microorganisms spoil food?",
            "Give two methods of food preservation.",
            "Which method keeps food very cold: freezing, drying, or salting?",
            "True or false: Food preservation can slow down microorganism growth.",
            "Why does drying help preserve food?",
            "Give one daily-life example of preserved food.",
        ),
        misconceptions=(
            "Wrong idea: food preservation makes food last forever. Correction: it helps food last longer, but not forever.",
            "Wrong idea: only refrigerators preserve food. Correction: many methods can preserve food.",
            "Wrong idea: all microorganisms in food are useful. Correction: some can spoil food and make us sick.",
            "Wrong idea: spoiled food is always safe if it looks normal. Correction: spoiled or contaminated food can be unsafe.",
        ),
        key_terms=(
            ("Food preservation", "உணவு பாதுகாப்பு", "Ways to make food last longer."),
            ("Spoilage", "கெட்டுப்போவது", "When food becomes bad or unsafe."),
            ("Drying", "உலர்த்துதல்", "Removing water from food."),
            ("Boiling", "கொதிக்கவைத்தல்", "Heating food or liquid strongly."),
            ("Cooling", "குளிர்வித்தல்", "Keeping food cool."),
            ("Freezing", "உறையவைத்தல்", "Keeping food very cold until it freezes."),
            ("Salting", "உப்பு சேர்த்தல்", "Using salt to preserve food."),
            ("Pickling", "ஊறுகாய் செய்தல்", "Preserving food using vinegar, salt, or sugar."),
            ("Smoking", "புகையூட்டுதல்", "Using smoke to preserve food."),
            ("Pasteurisation", "பாஸ்சுரைசேஷன்", "Heating liquid food to reduce harmful microorganisms."),
        ),
    ),
)


def _now() -> datetime:
    return datetime.now()


def _iso_now() -> str:
    return _now().isoformat(timespec="seconds")


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "unknown"


def _ensure_dirs() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGEBASE_DIR.mkdir(parents=True, exist_ok=True)


def _load_manifest() -> dict[str, Any]:
    _ensure_dirs()
    if not MANIFEST_PATH.exists():
        return {"version": 1, "sources": {}}
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "sources": {}}
    if not isinstance(data, dict):
        return {"version": 1, "sources": {}}
    data.setdefault("version", 1)
    data.setdefault("sources", {})
    return data


def _save_manifest(manifest: dict[str, Any]) -> None:
    _ensure_dirs()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_files() -> list[Path]:
    _ensure_dirs()
    files: list[Path] = []
    for path in SOURCE_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.name == MANIFEST_PATH.name or path.name.startswith("conversion_log_"):
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(path)
    return sorted(files, key=lambda item: _relative(item).lower())


def _debug_scan_info(files: list[Path]) -> dict[str, Any]:
    return {
        "project_root": str(ROOT_DIR),
        "knowledge_sources_dir": str(SOURCE_DIR),
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "detected_source_files": [_relative(path) for path in files],
    }


def _source_info(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "file_path": _relative(path),
        "file_name": path.name,
        "file_size": stat.st_size,
        "last_modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "content_hash": _hash_file(path),
    }


def _detect_subject_level(path: Path) -> tuple[str, str]:
    try:
        relative_parts = path.relative_to(SOURCE_DIR).parts
    except ValueError:
        relative_parts = path.parts
    haystack = " ".join(part.lower() for part in relative_parts)
    subject = "science" if any(token in haystack for token in ("science", "sains")) else "science"
    year_match = re.search(r"(?:^|[^a-z0-9])(?:science[_\-\s]*)?(?:year|tahun|yr|t)[_\-\s]*([1-6])(?:[^a-z0-9]|$)", haystack)
    if not year_match:
        year_match = re.search(r"(?:^|[^a-z0-9])([1-6])(?:[^a-z0-9]|$)", haystack)
    level = f"year{year_match.group(1)}" if year_match else "year6"
    return subject, level


def _read_pdf(path: Path) -> tuple[str, list[str]]:
    errors: list[str] = []
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - dependency environment guard
        return "", [f"PDF reader unavailable: {type(exc).__name__}"]
    try:
        reader = PdfReader(str(path))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:
                errors.append(f"Page {index} extraction failed: {type(exc).__name__}")
        return "\n\n".join(pages), errors
    except Exception as exc:
        return "", [f"PDF extraction failed: {type(exc).__name__}: {exc}"]


def _read_docx(path: Path) -> tuple[str, list[str]]:
    try:
        from docx import Document
        doc = Document(str(path))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs), []
    except Exception as exc:
        return "", [f"DOCX extraction failed: {type(exc).__name__}: {exc}"]


def _read_xlsx(path: Path) -> tuple[str, list[str]]:
    try:
        from openpyxl import load_workbook
        workbook = load_workbook(filename=str(path), read_only=True, data_only=True)
        rows: list[str] = []
        for sheet in workbook.worksheets:
            rows.append(f"Sheet: {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                values = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
                if values:
                    rows.append(" | ".join(values))
        workbook.close()
        return "\n".join(rows), []
    except Exception as exc:
        return "", [f"XLSX extraction failed: {type(exc).__name__}: {exc}"]


def _extract_text(path: Path) -> tuple[str, list[str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    if suffix == ".xlsx":
        return _read_xlsx(path)
    if suffix == ".txt":
        try:
            return path.read_text(encoding="utf-8", errors="replace"), []
        except Exception as exc:
            return "", [f"TXT extraction failed: {type(exc).__name__}: {exc}"]
    return "", [f"Unsupported file type: {suffix}"]


def _clean_text(text: str) -> str:
    cleaned = text.replace("\x00", " ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _paragraphs(text: str) -> list[str]:
    chunks = re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-Z])", text)
    return [re.sub(r"\s+", " ", chunk).strip() for chunk in chunks if len(chunk.strip()) > 40]


def _topic_source_signals(text: str, topic: TopicSpec) -> tuple[list[str], bool]:
    lowered_keywords = [keyword.lower() for keyword in topic.keywords]
    matches: list[str] = []
    for paragraph in _paragraphs(text):
        low = paragraph.lower()
        if any(keyword in low for keyword in lowered_keywords):
            matches.append(paragraph[:350])
        if len(matches) >= 8:
            break
    needs_review = len(matches) < 2
    return matches, needs_review


def _source_summary(topic: TopicSpec, signals: list[str], needs_review: bool) -> str:
    if needs_review:
        return (
            "NEEDS_REVIEW: Extracted text did not clearly provide enough readable source content for this topic. "
            "Generated learning support below is based on the expected Year 6 Science topic scope and should be reviewed against the source."
        )
    bullets = "\n".join(f"- Source signal: {signal}" for signal in signals[:4])
    return f"Short source signals used for conversion:\n{bullets}"


def _note_content(source_name: str, topic: TopicSpec, signals: list[str], needs_review: bool) -> str:
    review = "\nNEEDS_REVIEW: Check diagrams, tables, image labels, and OCR-sensitive sections.\n" if needs_review else ""
    notes = "\n".join(f"- {line}" for line in topic.notes)
    return f"""Topic: {topic.title}
Source: {source_name}
Generated by AI-EZAM source converter.
{review}
Source reference:
{_source_summary(topic, signals, needs_review)}

Teaching notes:
{notes}

Tutor guidance:
- Use these notes as reference, not as a fixed script.
- Explain with short, student-friendly examples.
- If the student gives a wrong example, clarify why it is wrong before asking another question.
- Do not expose raw source chunks to the student.
"""


def _question_bank_content(source_name: str, topic: TopicSpec, needs_review: bool) -> str:
    review = "\nNEEDS_REVIEW: Review generated questions against the source before classroom use.\n" if needs_review else ""
    questions = "\n".join(f"- {question}" for question in topic.questions)
    return f"""Topic: {topic.title}
Source: {source_name}
Generated by AI-EZAM source converter.
{review}
Learning-mode and practice questions:
{questions}
"""


def _misconceptions_content(source_name: str, topic: TopicSpec, needs_review: bool) -> str:
    review = "\nNEEDS_REVIEW: Review misconception guidance against source diagrams and examples.\n" if needs_review else ""
    items = "\n".join(f"- {item}" for item in topic.misconceptions)
    return f"""Topic: {topic.title}
Source: {source_name}
Generated by AI-EZAM source converter.
{review}
Common misconceptions and correction guidance:
{items}
"""


def _key_terms_content(source_name: str, topic: TopicSpec, needs_review: bool) -> str:
    review = "\nNEEDS_REVIEW: Review Tamil terms for local classroom preference.\n" if needs_review else ""
    rows = "\n".join(f"- {english} = {tamil} | {meaning}" for english, tamil, meaning in topic.key_terms)
    return f"""Topic: {topic.title}
Source: {source_name}
Generated by AI-EZAM source converter.
{review}
Key terms:
{rows}

Tamil wording guidance:
- Prefer simple Tamil suitable for SJKT Year 6 students.
- Keep English science terms only when commonly used in class.
"""


def _topic_files(source_name: str, topic: TopicSpec, signals: list[str], needs_review: bool) -> dict[str, str]:
    return {
        "note.txt": _note_content(source_name, topic, signals, needs_review),
        "question_bank.txt": _question_bank_content(source_name, topic, needs_review),
        "misconceptions.txt": _misconceptions_content(source_name, topic, needs_review),
        "key_terms.txt": _key_terms_content(source_name, topic, needs_review),
    }


QUESTION_HEADERS = [
    "question_id",
    "subject",
    "level",
    "topic",
    "concept",
    "difficulty",
    "question_type",
    "question_text",
    "expected_answer",
    "keywords",
    "hint",
    "explanation",
    "misconception_tag",
    "followup_question_id",
    "marks",
    "mode",
]


def _question_meta(topic: TopicSpec, question_text: str, index: int) -> dict[str, Any]:
    text = question_text.lower()
    if topic.key == "microorganisms":
        if "what are microorganisms" in text:
            return {
                "concept": "types",
                "difficulty": "easy",
                "question_type": "short_answer",
                "expected_answer": "tiny living things, too small to be seen clearly",
                "keywords": "tiny,living things,small,microscope",
                "hint": "Think about size and living things.",
                "explanation": "Microorganisms are tiny living things that are usually too small to see clearly with only our eyes.",
                "misconception_tag": "definition_unclear",
                "followup_question_id": f"{topic.key}_q2",
                "marks": 2,
                "mode": "both",
            }
        if "which one is a microorganism" in text:
            qtype = "mcq"
            expected = "bacteria"
            keywords = "bacteria"
        elif "true or false" in text or "all microorganisms are harmful" in text:
            qtype = "true_false"
            expected = "false, not all microorganisms are harmful"
            keywords = "false,useful,harmful"
        elif "bird" in text:
            qtype = "short_answer"
            expected = "no, birds are visible animals"
            keywords = "no,visible,animal"
        elif "air" in text:
            qtype = "short_answer"
            expected = "air is not living"
            keywords = "air,not living"
        elif "bread" in text:
            qtype = "short_answer"
            expected = "yeast"
            keywords = "yeast,bread"
        else:
            qtype = "short_answer"
            expected = "microorganism example or explanation"
            keywords = "bacteria,virus,fungi,yeast,algae,protozoa,microscope"
        return {
            "concept": "types" if index <= 7 else "useful_vs_harmful",
            "difficulty": "easy",
            "question_type": qtype,
            "expected_answer": expected,
            "keywords": keywords,
            "hint": "Use the Year 6 microorganisms idea.",
            "explanation": "Use the notes to check whether the answer matches the microorganism concept.",
            "misconception_tag": "microorganism_confusion",
            "followup_question_id": "",
            "marks": 1,
            "mode": "both",
        }
    if topic.key == "food_preservation":
        if "which method" in text:
            qtype = "mcq"
            expected = "freezing"
        elif "true or false" in text:
            qtype = "true_false"
            expected = "true"
        else:
            qtype = "short_answer"
            expected = "food preservation slows spoilage or microorganism growth"
        return {
            "concept": "food_preservation",
            "difficulty": "easy",
            "question_type": qtype,
            "expected_answer": expected,
            "keywords": "preserve,food,spoilage,microorganisms,drying,freezing,salting",
            "hint": "Think about how food is kept safe for longer.",
            "explanation": "Food preservation helps food last longer by slowing or stopping spoilage.",
            "misconception_tag": "food_preservation_confusion",
            "followup_question_id": "",
            "marks": 1,
            "mode": "both",
        }
    if "which is an example" in text:
        qtype = "mcq"
        expected = "a bird eating a worm"
    elif "true or false" in text:
        qtype = "true_false"
        expected = "false"
    else:
        qtype = "short_answer"
        expected = "living things interact for food, water, shelter, space, or protection"
    return {
        "concept": "relationships",
        "difficulty": "easy",
        "question_type": qtype,
        "expected_answer": expected,
        "keywords": "living things,relationship,competition,predator,prey,food",
        "hint": "Think about how living things depend on each other.",
        "explanation": "Living things interact with one another to get what they need.",
        "misconception_tag": "relationship_confusion",
        "followup_question_id": "",
        "marks": 1,
        "mode": "both",
    }


def _question_rows(subject: str, level: str, topic: TopicSpec, topic_name: str) -> list[list[Any]]:
    rows = [QUESTION_HEADERS]
    for index, question_text in enumerate(topic.questions, start=1):
        meta = _question_meta(topic, question_text, index)
        rows.append([
            f"{topic.key}_q{index}",
            subject,
            level,
            topic_name,
            meta["concept"],
            meta["difficulty"],
            meta["question_type"],
            question_text,
            meta["expected_answer"],
            meta["keywords"],
            meta["hint"],
            meta["explanation"],
            meta["misconception_tag"],
            meta["followup_question_id"],
            meta["marks"],
            meta["mode"],
        ])
    return rows


def _write_question_bank_xlsx(
    *,
    topic_dir: Path,
    subject: str,
    level: str,
    topic: TopicSpec,
    topic_name: str,
    overwrite: bool,
) -> tuple[list[str], list[str]]:
    from openpyxl import Workbook

    questions_dir = topic_dir / "questions"
    target = questions_dir / "question_bank.xlsx"
    if target.exists() and not overwrite:
        return [], [_relative(target)]

    questions_dir.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "questions"
    for row in _question_rows(subject, level, topic, topic_name):
        sheet.append(row)
    workbook.save(str(target))
    workbook.close()
    return [_relative(target)], []


def _required_question_banks_exist(prior: dict[str, Any]) -> bool:
    output_topics = prior.get("output_topics_created") or []
    if not output_topics:
        return False
    for topic_path in output_topics:
        target = ROOT_DIR / str(topic_path) / "questions" / "question_bank.xlsx"
        if not target.exists():
            return False
    return True


def _topic_for_folder_name(folder_name: str) -> Optional[TopicSpec]:
    for topic in TOPICS:
        if folder_name in {topic.folder, topic.key}:
            return topic
    return None


def _repair_missing_question_banks(prior: dict[str, Any], *, overwrite: bool) -> dict[str, Any]:
    topics_created: list[str] = []
    files_written: list[str] = []
    files_skipped: list[str] = []
    errors: list[str] = []

    for topic_path in prior.get("output_topics_created", []):
        topic_dir = ROOT_DIR / str(topic_path)
        try:
            subject, level, topic_name = topic_dir.relative_to(KNOWLEDGEBASE_DIR).parts[:3]
        except (ValueError, IndexError):
            errors.append(f"Cannot repair question bank for unexpected topic path: {topic_path}")
            continue

        topic = _topic_for_folder_name(topic_name)
        if topic is None:
            errors.append(f"Cannot repair question bank for unknown topic folder: {topic_name}")
            continue

        xlsx_written, xlsx_skipped = _write_question_bank_xlsx(
            topic_dir=topic_dir,
            subject=subject,
            level=level,
            topic=topic,
            topic_name=topic_name,
            overwrite=overwrite,
        )
        topics_created.append(_relative(topic_dir))
        files_written.extend(xlsx_written)
        files_skipped.extend(xlsx_skipped)

    return {
        "output_topics_created": topics_created,
        "files_written": files_written,
        "draft_files_created": [],
        "files_skipped": files_skipped,
        "needs_review_sections": [],
        "errors": errors,
    }


def _next_draft_path(base_path: Path, hash_prefix: str) -> Path:
    draft = base_path.with_name(f"{base_path.stem}.generated{base_path.suffix}")
    if not draft.exists():
        return draft
    hashed = base_path.with_name(f"{base_path.stem}.generated.{hash_prefix}{base_path.suffix}")
    if not hashed.exists():
        return hashed
    counter = 2
    while True:
        candidate = base_path.with_name(f"{base_path.stem}.generated.{hash_prefix}.{counter}{base_path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _write_topic_files(
    *,
    topic_dir: Path,
    files: dict[str, str],
    overwrite: bool,
    hash_prefix: str,
) -> tuple[list[str], list[str], list[str]]:
    written: list[str] = []
    drafts: list[str] = []
    skipped: list[str] = []
    topic_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        target = topic_dir / name
        if overwrite or not target.exists():
            target.write_text(content, encoding="utf-8")
            written.append(_relative(target))
            continue
        draft = _next_draft_path(target, hash_prefix)
        draft.write_text(content, encoding="utf-8")
        drafts.append(_relative(draft))
        skipped.append(_relative(target))
    return written, drafts, skipped


def _convert_file(path: Path, info: dict[str, Any], *, overwrite: bool) -> dict[str, Any]:
    subject, level = _detect_subject_level(path)
    text, errors = _extract_text(path)
    text = _clean_text(text)
    hash_prefix = str(info["content_hash"])[:10]
    topics_created: list[str] = []
    files_written: list[str] = []
    draft_files_created: list[str] = []
    files_skipped: list[str] = []
    needs_review_sections: list[str] = []

    if not text or len(text) < 500:
        errors.append("Extracted text is short or empty; topic content may need OCR/manual review.")

    for topic in TOPICS:
        signals, needs_review = _topic_source_signals(text, topic)
        if needs_review:
            needs_review_sections.append(topic.key)
        topic_dirs = [(topic.folder, KNOWLEDGEBASE_DIR / subject / level / topic.folder)]
        alias_dir = KNOWLEDGEBASE_DIR / subject / level / topic.key
        if topic.key != topic.folder and not alias_dir.exists():
            topic_dirs.append((topic.key, alias_dir))

        for topic_name, topic_dir in topic_dirs:
            files = _topic_files(path.name, topic, signals, needs_review)
            written, drafts, skipped = _write_topic_files(
                topic_dir=topic_dir,
                files=files,
                overwrite=overwrite,
                hash_prefix=hash_prefix,
            )
            xlsx_written, xlsx_skipped = _write_question_bank_xlsx(
                topic_dir=topic_dir,
                subject=subject,
                level=level,
                topic=topic,
                topic_name=topic_name,
                overwrite=overwrite,
            )
            topics_created.append(_relative(topic_dir))
            files_written.extend(written)
            files_written.extend(xlsx_written)
            draft_files_created.extend(drafts)
            files_skipped.extend(skipped)
            files_skipped.extend(xlsx_skipped)

    return {
        "source_file": _relative(path),
        "subject": subject,
        "level": level,
        "output_topics_created": topics_created,
        "files_written": files_written,
        "draft_files_created": draft_files_created,
        "files_skipped": files_skipped,
        "needs_review_sections": needs_review_sections,
        "errors": errors,
    }


def _empty_summary(update: bool, overwrite: bool, files: Optional[list[Path]] = None) -> dict[str, Any]:
    detected_files = files or []
    return {
        "ok": True,
        "mode": {"update": update, "overwrite": overwrite},
        **_debug_scan_info(detected_files),
        "source_files_scanned": 0,
        "new_files_converted": 0,
        "existing_files_skipped": 0,
        "modified_files_detected": 0,
        "topics_created": 0,
        "draft_files_created": 0,
        "needs_review": 0,
        "errors_count": 0,
        "files": [],
        "errors": [],
        "message": "No supported source files found in knowledge_sources/. Supported files may be inside subfolders and must end with .pdf, .docx, .txt, or .xlsx.",
        "next_step": "Add source files to knowledge_sources/, then run Generate Knowledgebase again.",
    }


def _append_daily_log(summary: dict[str, Any]) -> None:
    _ensure_dirs()
    log_path = SOURCE_DIR / f"conversion_log_{_now().date().isoformat()}.txt"
    lines = [
        "=" * 72,
        f"timestamp: {_iso_now()}",
        f"mode: update={summary['mode']['update']} overwrite={summary['mode']['overwrite']}",
        f"source_files_scanned: {summary['source_files_scanned']}",
        f"new_files_converted: {summary['new_files_converted']}",
        f"existing_files_skipped: {summary['existing_files_skipped']}",
        f"modified_files_detected: {summary['modified_files_detected']}",
        f"topics_created: {summary['topics_created']}",
        f"draft_files_created: {summary['draft_files_created']}",
        f"needs_review: {summary['needs_review']}",
        f"errors_count: {summary['errors_count']}",
    ]
    for item in summary.get("files", []):
        lines.extend([
            "",
            f"source file name: {item.get('file_name', '')}",
            f"source file hash: {item.get('content_hash', '')}",
            f"status: {item.get('status', '')}",
            f"output folders created: {', '.join(item.get('output_topics_created', []))}",
            f"files skipped: {', '.join(item.get('files_skipped', []))}",
            f"modified files detected: {item.get('status') == 'UPDATED SOURCE DETECTED'}",
            f"errors: {', '.join(item.get('errors', []))}",
            f"sections marked NEEDS_REVIEW: {', '.join(item.get('needs_review_sections', []))}",
        ])
    lines.append("Next step: Click Rebuild Index before testing AI-EZAM.")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def get_source_status() -> dict[str, Any]:
    manifest = _load_manifest()
    source_paths = _source_files()
    files = []
    for path in source_paths:
        info = _source_info(path)
        prior = manifest.get("sources", {}).get(info["file_path"])
        if not prior:
            status = "NEW"
        elif prior.get("content_hash") == info["content_hash"]:
            status = "CONVERTED"
        else:
            status = "MODIFIED"
        files.append({**info, "status": status})
    return {
        "ok": True,
        **_debug_scan_info(source_paths),
        "source_folder": _relative(SOURCE_DIR),
        "manifest_path": _relative(MANIFEST_PATH),
        "files": files,
        "source_files_scanned": len(files),
    }


def convert_sources(*, update: bool = False, overwrite: bool = False) -> dict[str, Any]:
    _ensure_dirs()
    manifest = _load_manifest()
    sources = manifest.setdefault("sources", {})
    files = _source_files()
    if not files:
        summary = _empty_summary(update, overwrite, files)
        _append_daily_log(summary)
        _save_manifest(manifest)
        return summary

    summary = _empty_summary(update, overwrite, files)
    summary.update({
        "source_files_scanned": len(files),
        "message": "",
        "next_step": "Click Rebuild Index before starting a session.",
    })

    for path in files:
        info = _source_info(path)
        prior = sources.get(info["file_path"])
        file_record = dict(info)
        file_record.update({
            "status": "",
            "output_topics_created": [],
            "files_written": [],
            "draft_files_created": [],
            "files_skipped": [],
            "needs_review_sections": [],
            "errors": [],
        })

        should_convert = False
        repair_missing_question_banks = False
        if overwrite:
            file_record["status"] = "CONVERTED - overwrite mode"
            should_convert = True
        elif not prior:
            file_record["status"] = "CONVERTED - new file"
            should_convert = True
            summary["new_files_converted"] += 1
        elif prior.get("content_hash") == info["content_hash"]:
            if _required_question_banks_exist(prior):
                file_record["status"] = "SKIPPED - already converted"
                file_record["output_topics_created"] = prior.get("output_topics_created", [])
                summary["existing_files_skipped"] += 1
            else:
                file_record["status"] = "CONVERTED - repaired missing question bank"
                repair_missing_question_banks = True
        else:
            summary["modified_files_detected"] += 1
            if update:
                file_record["status"] = "CONVERTED - updated source"
                should_convert = True
            else:
                file_record["status"] = "UPDATED SOURCE DETECTED"

        if should_convert:
            try:
                converted = _convert_file(path, info, overwrite=overwrite)
                file_record.update(converted)
                summary["topics_created"] += len(converted["output_topics_created"])
                summary["draft_files_created"] += len(converted["draft_files_created"])
                summary["needs_review"] += len(converted["needs_review_sections"])
                summary["errors_count"] += len(converted["errors"])
                summary["errors"].extend(converted["errors"])
                sources[info["file_path"]] = {
                    **info,
                    "converted_at": _iso_now(),
                    "output_topics_created": converted["output_topics_created"],
                    "status": file_record["status"],
                }
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                file_record["status"] = "ERROR"
                file_record["errors"].append(message)
                summary["errors"].append(message)
                summary["errors_count"] += 1
        elif repair_missing_question_banks:
            try:
                converted = _repair_missing_question_banks(prior, overwrite=overwrite)
                file_record.update(converted)
                summary["topics_created"] += len(converted["output_topics_created"])
                summary["draft_files_created"] += len(converted["draft_files_created"])
                summary["needs_review"] += len(converted["needs_review_sections"])
                summary["errors_count"] += len(converted["errors"])
                summary["errors"].extend(converted["errors"])
                sources[info["file_path"]] = {
                    **info,
                    "converted_at": _iso_now(),
                    "output_topics_created": converted["output_topics_created"],
                    "status": file_record["status"],
                }
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                file_record["status"] = "ERROR"
                file_record["errors"].append(message)
                summary["errors"].append(message)
                summary["errors_count"] += 1

        summary["files"].append(file_record)

    if summary["new_files_converted"] == 0 and summary["modified_files_detected"] == 0 and summary["existing_files_skipped"] > 0:
        summary["message"] = "No new source files found. Existing converted files were skipped."
    else:
        summary["message"] = "Knowledgebase generation completed."
    summary["reminder"] = "Please click Rebuild Index before starting a session."
    _save_manifest(manifest)
    _append_daily_log(summary)
    return summary


def _print_summary(summary: dict[str, Any]) -> None:
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\nNext step: Click Rebuild Index before testing AI-EZAM.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert AI-EZAM source files into structured knowledgebase topics.")
    parser.add_argument("--update", action="store_true", help="Convert new and modified source files.")
    parser.add_argument("--overwrite", action="store_true", help="Reconvert everything and overwrite generated output files.")
    args = parser.parse_args()
    summary = convert_sources(update=args.update, overwrite=args.overwrite)
    _print_summary(summary)


if __name__ == "__main__":
    main()
