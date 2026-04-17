from __future__ import annotations


def parse_image(file_path: str) -> dict[str, str | None]:
    return {
        "parser": "image_parser",
        "status": "placeholder",
        "message": "Image OCR is not implemented in the MVP; metadata is preserved.",
        "extracted_text_preview": None,
    }
