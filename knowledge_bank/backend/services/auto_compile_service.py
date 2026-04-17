from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from backend.config import get_processed_storage_root
from backend.models.source import Source
from backend.schemas.knowledge_unit import CompiledKnowledgeUnitInput
from backend.services.file_parsers.code_parser import extract_code_text
from backend.services.file_parsers.pdf_parser import stream_pdf_pages
from backend.services.file_parsers.text_parser import extract_text_content
from backend.services.text_chunking import chunk_text

logger = logging.getLogger(__name__)

_LINE_NOISE_PATTERNS = [
    re.compile(r"^Hackeling, Gavin\.", re.IGNORECASE),
    re.compile(r"^Created from durham", re.IGNORECASE),
    re.compile(r"^Copyright © 2017\. Packt Publishing", re.IGNORECASE),
    re.compile(r"ebookcentral\.proquest\.com", re.IGNORECASE),
    re.compile(r"detail\.action\?docID=", re.IGNORECASE),
]
_TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "other",
    "the",
    "to",
    "with",
}
_GENERIC_TAG_WORDS = {
    "chapter",
    "classification",
    "classifying",
    "learning",
    "machine",
    "model",
    "models",
    "regression",
    "summary",
    "using",
}


@dataclass(frozen=True)
class ProcessedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class TocEntry:
    key: str
    title: str
    anchor_title: str
    printed_page: int
    pdf_page: int
    kind: str
    chapter_key: str | None
    chapter_title: str | None


@dataclass(frozen=True)
class GeneratedCompiledUnit:
    key: str
    payload: CompiledKnowledgeUnitInput
    prerequisite_keys: list[str]


def _get_processed_source_dir(source: Source) -> Path:
    path = get_processed_storage_root() / source.source_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _clean_line(line: str) -> str:
    normalized = " ".join(line.strip().split())
    if not normalized:
        return ""
    if re.fullmatch(r"\[\s*[ivxlcdmIVXLCDM0-9]+\s*\]", normalized):
        return ""
    for pattern in _LINE_NOISE_PATTERNS:
        if pattern.search(normalized):
            return ""
    return normalized


def _clean_text_block(text: str) -> str:
    cleaned_lines = [_clean_line(line) for line in text.splitlines()]
    return "\n".join(line for line in cleaned_lines if line).strip()


def _slugify(text: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", text.lower())
    return "_".join(parts[:10]) or "unit"


def _truncate_text(text: str, max_chars: int) -> str:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped
    clipped = stripped[:max_chars].rsplit(" ", 1)[0].strip()
    return f"{clipped}..."


def _extract_summary(text: str) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return "Auto-generated summary is unavailable."
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    summary = " ".join(sentence.strip() for sentence in sentences[:2] if sentence.strip()).strip()
    if not summary:
        summary = normalized[:320]
    return _truncate_text(summary, 360)


def _derive_pedagogical_role(title: str, kind: str) -> str:
    lowered = title.lower()
    if any(token in lowered for token in ["advantage", "disadvantage", "limitation", "bias", "variance"]):
        return "caution"
    if any(
        token in lowered
        for token in [
            "using",
            "applying",
            "training",
            "classifying",
            "classification with",
            "regression with",
            "visualizing",
            "installing",
            "performing",
        ]
    ):
        return "example"
    if kind == "chapter" and any(token in lowered for token in ["fundamental", "introduction", "basics"]):
        return "prerequisite"
    return "concept"


def _derive_topic_tags(title: str, chapter_title: str | None) -> list[str]:
    tags: list[str] = []
    for candidate in [title, chapter_title]:
        if not candidate:
            continue
        slug = _slugify(candidate)
        if slug not in tags:
            tags.append(slug)

    for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]+", title.lower()):
        cleaned = word.replace("-", "_")
        if len(cleaned) < 4 or cleaned in _TITLE_STOPWORDS or cleaned in _GENERIC_TAG_WORDS:
            continue
        if cleaned not in tags:
            tags.append(cleaned)
        if len(tags) >= 6:
            break
    return tags or ["knowledge_unit"]


def _extract_source_text(source: Source) -> str | None:
    if source.source_type == "text":
        return extract_text_content(source.storage_path)
    if source.source_type == "code":
        return extract_code_text(source.storage_path)
    return None


def _load_page_records(processed_dir: Path) -> list[ProcessedPage]:
    page_manifest = processed_dir / "page_texts.jsonl"
    if not page_manifest.exists():
        return []

    records: list[ProcessedPage] = []
    for line in page_manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        records.append(
            ProcessedPage(
                page_number=int(payload["page_number"]),
                text=str(payload.get("text", "")),
            )
        )
    return records


def _load_expected_page_count(processed_dir: Path) -> int | None:
    extraction_summary = processed_dir / "extraction_summary.json"
    if not extraction_summary.exists():
        return None
    try:
        payload = json.loads(extraction_summary.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    page_count = payload.get("page_count")
    return int(page_count) if isinstance(page_count, int) else None


def _persist_pdf_pages(source: Source, processed_dir: Path) -> list[ProcessedPage]:
    streamed = stream_pdf_pages(source.storage_path)
    if not streamed:
        return []

    total_pages, pages_iter = streamed
    page_manifest = processed_dir / "page_texts.jsonl"
    page_manifest.write_text("", encoding="utf-8")

    records: list[ProcessedPage] = []
    for page in pages_iter:
        records.append(ProcessedPage(page_number=page.page_number, text=page.text))
        _append_jsonl(
            page_manifest,
            {
                "page_number": page.page_number,
                "char_count": len(page.text),
                "text": page.text,
            },
        )

    _write_json(
        processed_dir / "extraction_summary.json",
        {
            "source_id": source.source_id,
            "source_type": source.source_type,
            "page_count": total_pages,
            "non_empty_page_count": len([item for item in records if item.text.strip()]),
            "extracted_char_count": sum(len(item.text) for item in records),
        },
    )
    return records


def _ensure_page_records(source: Source) -> list[ProcessedPage]:
    processed_dir = _get_processed_source_dir(source)
    records = _load_page_records(processed_dir)
    expected_page_count = _load_expected_page_count(processed_dir)
    if records and (expected_page_count is None or len(records) >= expected_page_count):
        return records
    if source.source_type != "pdf":
        return []
    if records and expected_page_count and len(records) < expected_page_count:
        logger.warning(
            "page manifest is incomplete and will be rebuilt: source_id=%s actual=%s expected=%s",
            source.source_id,
            len(records),
            expected_page_count,
        )
    return _persist_pdf_pages(source, processed_dir)


def _infer_printed_page_offset(page_records: list[ProcessedPage]) -> int | None:
    offsets: Counter[int] = Counter()
    for page in page_records:
        for line in page.text.splitlines()[:6]:
            match = re.fullmatch(r"\[\s*(\d+)\s*\]", line.strip())
            if not match:
                continue
            offset = page.page_number - int(match.group(1))
            if 0 <= offset <= 40:
                offsets[offset] += 1
    if not offsets:
        return None
    return offsets.most_common(1)[0][0]


def _extract_toc_entries(page_records: list[ProcessedPage]) -> list[tuple[str, int]]:
    toc_lines: list[str] = []
    started = False
    for page in page_records[:40]:
        cleaned = _clean_text_block(page.text)
        if not started and "Table of Contents" not in cleaned:
            continue
        started = True
        for raw_line in cleaned.splitlines():
            line = raw_line.strip()
            if not line or line == "Table of Contents":
                continue
            toc_lines.append(line)
            if re.fullmatch(r"Index\s+\d+", line):
                started = False
                break
        if not started and toc_lines:
            break

    merged_lines: list[str] = []
    buffer = ""
    for line in toc_lines:
        if re.search(r"\d+$", line):
            merged_lines.append(f"{buffer} {line}".strip() if buffer else line)
            buffer = ""
        else:
            buffer = f"{buffer} {line}".strip() if buffer else line

    entries: list[tuple[str, int]] = []
    for line in merged_lines:
        match = re.match(r"(.+?)\s+(\d+)$", line)
        if not match:
            continue
        title = match.group(1).strip()
        title = re.sub(r"^Publishing, Limited, 2017\.\s*", "", title)
        if title.lower() in {"preface", "index"}:
            continue
        if not title:
            continue
        entries.append((title, int(match.group(2))))
    return entries


def _build_structured_toc(entries: list[tuple[str, int]], printed_offset: int) -> list[TocEntry]:
    structured: list[TocEntry] = []
    chapter_key: str | None = None
    chapter_title: str | None = None
    chapter_counter = 0
    section_counter = 0

    for raw_title, printed_page in entries:
        if raw_title.startswith("Chapter "):
            chapter_counter += 1
            chapter_key = f"chapter_{chapter_counter}_{_slugify(raw_title)}"
            chapter_title = raw_title.split(": ", 1)[1].strip() if ": " in raw_title else raw_title
            structured.append(
                TocEntry(
                    key=chapter_key,
                    title=raw_title,
                    anchor_title=chapter_title,
                    printed_page=printed_page,
                    pdf_page=printed_page + printed_offset,
                    kind="chapter",
                    chapter_key=chapter_key,
                    chapter_title=chapter_title,
                )
            )
            continue

        section_counter += 1
        structured.append(
            TocEntry(
                key=f"section_{section_counter}_{_slugify(raw_title)}",
                title=raw_title,
                anchor_title=raw_title,
                printed_page=printed_page,
                pdf_page=printed_page + printed_offset,
                kind="section",
                chapter_key=chapter_key,
                chapter_title=chapter_title,
            )
        )

    return structured


def _combine_pages(page_records: list[ProcessedPage]) -> tuple[str, dict[int, int]]:
    parts: list[str] = []
    page_starts: dict[int, int] = {}
    cursor = 0
    for page in page_records:
        cleaned_text = _clean_text_block(page.text)
        page_starts[page.page_number] = cursor
        parts.append(cleaned_text)
        cursor += len(cleaned_text) + 2
    return "\n\n".join(parts), page_starts


def _build_title_pattern(anchor_title: str) -> re.Pattern[str]:
    words = re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?", anchor_title)
    escaped = r"\s+".join(re.escape(word) for word in words)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


def _locate_entry_spans(entries: list[TocEntry], combined_text: str, page_starts: dict[int, int]) -> list[tuple[TocEntry, int, int]]:
    spans: list[tuple[TocEntry, int, int]] = []
    previous_end = 0
    for index, entry in enumerate(entries):
        expected_start = page_starts.get(entry.pdf_page, previous_end)
        next_expected_start = (
            page_starts.get(entries[index + 1].pdf_page, len(combined_text))
            if index + 1 < len(entries)
            else len(combined_text)
        )
        lower_bound = max(previous_end, expected_start)
        upper_bound = min(len(combined_text), max(next_expected_start + 20000, expected_start + 12000))
        match = _build_title_pattern(entry.anchor_title).search(combined_text, lower_bound, upper_bound)
        if not match:
            fallback_lower = max(previous_end, expected_start)
            fallback_upper = min(len(combined_text), max(expected_start + 30000, upper_bound))
            match = _build_title_pattern(entry.anchor_title).search(combined_text, fallback_lower, fallback_upper)
        if not match:
            logger.info("auto compile skipped unmatched toc entry: title=%s page=%s", entry.title, entry.pdf_page)
            continue

        start = match.start()
        previous_end = max(previous_end, match.end())
        spans.append((entry, start, match.end()))

    return spans


def _build_units_from_toc(source: Source, page_records: list[ProcessedPage]) -> list[GeneratedCompiledUnit]:
    printed_offset = _infer_printed_page_offset(page_records)
    if printed_offset is None:
        return []

    raw_entries = _extract_toc_entries(page_records)
    if not raw_entries:
        return []

    entries = _build_structured_toc(raw_entries, printed_offset)
    combined_text, page_starts = _combine_pages(page_records)
    spans = _locate_entry_spans(entries, combined_text, page_starts)
    if not spans:
        return []

    generated_units: list[GeneratedCompiledUnit] = []
    previous_section_key_by_chapter: dict[str, str] = {}
    previous_chapter_key: str | None = None

    for index, (entry, start, _) in enumerate(spans):
        end = spans[index + 1][1] if index + 1 < len(spans) else len(combined_text)
        body_text = _clean_text_block(combined_text[start:end])
        if len(body_text) < 80:
            continue

        prerequisite_keys: list[str] = []
        if entry.kind == "chapter":
            if previous_chapter_key:
                prerequisite_keys.append(previous_chapter_key)
            previous_chapter_key = entry.key
        elif entry.chapter_key:
            prerequisite_keys.append(previous_section_key_by_chapter.get(entry.chapter_key, entry.chapter_key))
            previous_section_key_by_chapter[entry.chapter_key] = entry.key

        payload = CompiledKnowledgeUnitInput(
            title=entry.title,
            summary=_extract_summary(body_text),
            body_text=_truncate_text(body_text, 9000),
            module_tag=source.module_tag,
            week_tag=source.week_tag,
            topic_tags=_derive_topic_tags(entry.anchor_title, entry.chapter_title),
            difficulty_level="intro_undergrad",
            pedagogical_role=_derive_pedagogical_role(entry.title, entry.kind),
            source_type=source.source_type,
            source_ref=[source.source_id],
            prerequisite_links=[],
            learning_outcome_links=[],
        )
        generated_units.append(
            GeneratedCompiledUnit(
                key=entry.key,
                payload=payload,
                prerequisite_keys=[item for item in prerequisite_keys if item],
            )
        )

    return generated_units


def _split_text_sections(text: str) -> list[tuple[str, str]]:
    normalized_text = text.replace("\r\n", "\n")
    lines = [line.rstrip() for line in normalized_text.splitlines()]
    sections: list[tuple[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        if current_title and current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_title, body))
        current_title = None
        current_lines = []

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if current_title and current_lines and current_lines[-1]:
                current_lines.append("")
            continue

        markdown_match = re.match(r"^#{1,6}\s+(.+)$", stripped)
        heading_match = markdown_match or (
            re.match(r"^[A-Z][A-Za-z0-9 ,:()/_-]{2,88}$", stripped)
            if not stripped.endswith(".")
            else None
        )
        if heading_match:
            flush()
            current_title = heading_match.group(1).strip() if markdown_match else stripped
            continue

        if current_title is None:
            current_title = f"Section {len(sections) + 1}"
        current_lines.append(stripped)

    flush()
    return sections


def _build_units_from_sections(source: Source, sections: list[tuple[str, str]]) -> list[GeneratedCompiledUnit]:
    generated_units: list[GeneratedCompiledUnit] = []
    previous_key: str | None = None
    for index, (title, body_text) in enumerate(sections, start=1):
        cleaned_body = _clean_text_block(body_text)
        if len(cleaned_body) < 120:
            continue
        key = f"text_section_{index}_{_slugify(title)}"
        payload = CompiledKnowledgeUnitInput(
            title=title,
            summary=_extract_summary(cleaned_body),
            body_text=_truncate_text(cleaned_body, 7000),
            module_tag=source.module_tag,
            week_tag=source.week_tag,
            topic_tags=_derive_topic_tags(title, None),
            difficulty_level="intro_undergrad",
            pedagogical_role=_derive_pedagogical_role(title, "section"),
            source_type=source.source_type,
            source_ref=[source.source_id],
            prerequisite_links=[],
            learning_outcome_links=[],
        )
        prerequisite_keys = [previous_key] if previous_key else []
        generated_units.append(
            GeneratedCompiledUnit(
                key=key,
                payload=payload,
                prerequisite_keys=[item for item in prerequisite_keys if item],
            )
        )
        previous_key = key
    return generated_units


def _build_units_from_chunk_fallback(source: Source, text: str) -> list[GeneratedCompiledUnit]:
    chunks = chunk_text(text=text, chunk_size=2200, overlap=200)
    if not chunks:
        return []

    units: list[GeneratedCompiledUnit] = []
    previous_key: str | None = None
    for index, chunk in enumerate(chunks, start=1):
        cleaned_body = _clean_text_block(chunk.text)
        if not cleaned_body:
            continue
        title = f"{source.filename} chunk unit {index}"
        key = f"chunk_unit_{index}"
        units.append(
            GeneratedCompiledUnit(
                key=key,
                payload=CompiledKnowledgeUnitInput(
                    title=title,
                    summary=_extract_summary(cleaned_body),
                    body_text=_truncate_text(cleaned_body, 5000),
                    module_tag=source.module_tag,
                    week_tag=source.week_tag,
                    topic_tags=_derive_topic_tags(title, None),
                    difficulty_level="intro_undergrad",
                    pedagogical_role="concept",
                    source_type=source.source_type,
                    source_ref=[source.source_id],
                    prerequisite_links=[],
                    learning_outcome_links=[],
                ),
                prerequisite_keys=[previous_key] if previous_key else [],
            )
        )
        previous_key = key
    return units


def _persist_auto_compiled_payload(source: Source, generated_units: list[GeneratedCompiledUnit]) -> None:
    processed_dir = _get_processed_source_dir(source)
    payload = {
        "source_id": source.source_id,
        "compiled_units": [item.payload.model_dump(mode="json") for item in generated_units],
    }
    _write_json(processed_dir / "auto_compiled_units.json", payload)
    _write_json(
        processed_dir / "auto_compile_summary.json",
        {
            "source_id": source.source_id,
            "source_type": source.source_type,
            "generated_unit_count": len(generated_units),
            "titles": [item.payload.title for item in generated_units[:20]],
        },
    )


def build_generated_compiled_units(source: Source) -> list[GeneratedCompiledUnit]:
    page_records = _ensure_page_records(source)
    generated_units: list[GeneratedCompiledUnit] = []
    if page_records:
        generated_units = _build_units_from_toc(source, page_records)

    if not generated_units:
        source_text = _extract_source_text(source)
        if source_text:
            sections = _split_text_sections(source_text)
            generated_units = _build_units_from_sections(source, sections)
            if not generated_units:
                generated_units = _build_units_from_chunk_fallback(source, source_text)

    if generated_units:
        _persist_auto_compiled_payload(source, generated_units)
        logger.info(
            "auto compile generated units: source_id=%s count=%s",
            source.source_id,
            len(generated_units),
        )
    else:
        logger.info("auto compile produced no units: source_id=%s", source.source_id)
    return generated_units
