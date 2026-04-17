from __future__ import annotations

from pathlib import Path


def extract_code_text(file_path: str) -> str | None:
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:  # pragma: no cover - defensive fallback
        return None
    return content or None


def parse_code(file_path: str) -> dict[str, str | None]:
    content = extract_code_text(file_path)
    if content is None:
        return {
            "parser": "code_parser",
            "status": "fallback",
            "message": "Code file could not be read.",
            "extracted_text_preview": None,
        }

    preview = content[:1000] or None
    return {
        "parser": "code_parser",
        "status": "ok",
        "message": "Code file read as plain text.",
        "extracted_text_preview": preview,
    }
