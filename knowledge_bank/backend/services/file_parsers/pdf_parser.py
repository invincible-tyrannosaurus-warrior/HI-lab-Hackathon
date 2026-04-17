from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator
from pathlib import Path


@dataclass(frozen=True)
class PdfPageText:
    page_number: int
    text: str


def _load_pdf_reader(file_path: str):
    path = Path(file_path)
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return None

    try:
        return PdfReader(str(path))
    except Exception:  # pragma: no cover - defensive fallback
        return None


def stream_pdf_pages(file_path: str) -> tuple[int, Iterator[PdfPageText]] | None:
    reader = _load_pdf_reader(file_path)
    if reader is None:
        return None

    total_pages = len(reader.pages)

    def _iter_pages() -> Iterator[PdfPageText]:
        for index, page in enumerate(reader.pages, start=1):
            yield PdfPageText(page_number=index, text=(page.extract_text() or "").strip())

    return total_pages, _iter_pages()


def extract_pdf_pages(file_path: str) -> list[PdfPageText] | None:
    streamed = stream_pdf_pages(file_path)
    if streamed is None:
        return None
    _, pages_iter = streamed
    return list(pages_iter)


def extract_pdf_text(file_path: str) -> str | None:
    pages = extract_pdf_pages(file_path)
    if pages is None:
        return None
    text = "\n\n".join(page.text for page in pages if page.text).strip()
    return text or None


def parse_pdf(file_path: str) -> dict[str, str | None]:
    extracted_text = extract_pdf_text(file_path)
    if extracted_text is None:
        return {
            "parser": "pdf_parser",
            "status": "fallback",
            "message": "PDF text extraction is unavailable or failed; source was registered without extraction.",
            "extracted_text_preview": None,
        }
    preview = extracted_text[:1000] if extracted_text else None
    return {
        "parser": "pdf_parser",
        "status": "ok",
        "message": "PDF preview extracted.",
        "extracted_text_preview": preview,
    }
