from __future__ import annotations

from pathlib import Path


def test_upload_pdf_source(client, source_factory):
    source = source_factory("week3_entropy_notes.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF", "application/pdf")
    assert source["source_type"] == "pdf"
    assert source["hash"].startswith("sha256_")
    assert Path(source["storage_path"]).exists()


def test_upload_image_source(client, source_factory):
    source = source_factory("diagram.png", b"\x89PNG\r\n\x1a\nbinary", "image/png")
    assert source["source_type"] == "image"


def test_upload_code_source(client, source_factory):
    source = source_factory("example.py", b"print('hello world')\n", "text/x-python")
    assert source["source_type"] == "code"
