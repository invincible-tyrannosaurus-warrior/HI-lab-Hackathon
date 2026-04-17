from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    storage_root = tmp_path / "raw"
    vector_root = tmp_path / "vector"
    processed_root = tmp_path / "processed"
    monkeypatch.setenv("KB_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("KB_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("KB_VECTOR_STORE_ROOT", str(vector_root))
    monkeypatch.setenv("KB_PROCESSED_ROOT", str(processed_root))
    monkeypatch.setenv("KB_VECTOR_BACKEND", "memory")
    monkeypatch.setenv("KB_EMBEDDING_BACKEND", "mock")

    from backend.db.init_db import init_db
    from backend.db.session import configure_database
    from backend.main import app
    from backend.services.embedding_service import reset_embedding_client
    from backend.services.vector_store_service import reset_vector_store

    configure_database()
    reset_embedding_client()
    reset_vector_store()
    init_db(drop_existing=True)

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def source_factory(client):
    def _create(
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        module_tag: str = "Machine Learning",
        week_tag: str | None = "week_03",
        uploader: str = "tester",
    ):
        data = {"module_tag": module_tag, "uploader": uploader}
        if week_tag is not None:
            data["week_tag"] = week_tag
        response = client.post(
            "/sources/upload",
            data=data,
            files={"file": (filename, content, content_type)},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create


@pytest.fixture()
def compiled_units_payload():
    return [
        {
            "title": "Entropy intuition",
            "summary": "Entropy measures uncertainty.",
            "body_text": "Detailed explanation of entropy.",
            "topic_tags": ["decision_tree", "entropy"],
            "difficulty_level": "intro_undergrad",
            "pedagogical_role": "concept",
            "prerequisite_links": [],
            "learning_outcome_links": ["lo_entropy"],
        },
        {
            "title": "Entropy caution",
            "summary": "Entropy is not the same as noise.",
            "body_text": "Students often confuse entropy with arbitrary randomness.",
            "topic_tags": ["entropy"],
            "difficulty_level": "intro_undergrad",
            "pedagogical_role": "caution",
            "prerequisite_links": [],
            "learning_outcome_links": [],
        },
    ]


def create_knowledge(client: TestClient, source_id: str, compiled_units: list[dict]):
    response = client.post(
        "/knowledge/compile",
        json={"source_id": source_id, "compiled_units": compiled_units},
    )
    assert response.status_code == 200, response.text
    return response.json()
