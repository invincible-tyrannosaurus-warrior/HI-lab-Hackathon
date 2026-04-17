from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import create_knowledge


def test_compile_inserts_draft_knowledge_units(client, source_factory, compiled_units_payload):
    source = source_factory("week3_entropy_notes.pdf", b"%PDF-1.4\nstub", "application/pdf")
    compile_result = create_knowledge(client, source["source_id"], compiled_units_payload)

    assert compile_result["status"] == "stored"
    assert len(compile_result["created_knowledge_ids"]) == 2

    detail_response = client.get(f"/knowledge/{compile_result['created_knowledge_ids'][0]}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["approval_status"] == "draft"
    assert detail["topic_tags"] == ["decision_tree", "entropy"]
    assert detail["source_ref"] == [source["source_id"]]


def test_compile_auto_generates_units_from_preprocessed_pages(client, source_factory):
    source = source_factory("mini_reader.pdf", b"%PDF-1.4\nstub", "application/pdf")

    from backend.config import get_processed_storage_root

    source_dir = get_processed_storage_root() / source["source_id"]
    source_dir.mkdir(parents=True, exist_ok=True)
    page_records = [
        {
            "page_number": 1,
            "char_count": 112,
            "text": "\n".join(
                [
                    "Table of Contents",
                    "Chapter 1: Entropy Basics 1",
                    "Entropy intuition 1",
                    "Information gain 2",
                    "Summary 3",
                ]
            ),
        },
        {
            "page_number": 2,
            "char_count": 260,
            "text": "\n".join(
                [
                    "Entropy Basics",
                    "In this chapter we introduce uncertainty in classification and how entropy measures it.",
                    "Entropy intuition",
                    "Entropy measures the uncertainty of a variable and increases when outcomes are balanced.",
                    "It is a foundational idea for decision tree splitting.",
                ]
            ),
        },
        {
            "page_number": 3,
            "char_count": 210,
            "text": "\n".join(
                [
                    "Entropy Basics",
                    "[ 2 ]",
                    "Information gain",
                    "Information gain measures how much a split reduces entropy relative to the parent node.",
                    "It is used to compare candidate questions in a decision tree.",
                ]
            ),
        },
        {
            "page_number": 4,
            "char_count": 180,
            "text": "\n".join(
                [
                    "Entropy Basics",
                    "[ 3 ]",
                    "Summary",
                    "Entropy quantifies uncertainty and information gain scores candidate splits.",
                    "Together they support tree construction and explanation.",
                ]
            ),
        },
    ]
    page_manifest = source_dir / "page_texts.jsonl"
    page_manifest.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in page_records) + "\n",
        encoding="utf-8",
    )

    response = client.post("/knowledge/compile", json={"source_id": source["source_id"]})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "stored"
    assert len(payload["created_knowledge_ids"]) >= 3

    auto_payload_path = source_dir / "auto_compiled_units.json"
    assert auto_payload_path.exists()

    graph_response = client.get("/knowledge/graph")
    assert graph_response.status_code == 200
    graph = graph_response.json()
    assert any(edge["type"] == "prerequisite" for edge in graph["edges"])

    detail_response = client.get(f"/knowledge/{payload['created_knowledge_ids'][0]}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["source_ref"] == [source["source_id"]]
    assert detail["approval_status"] == "draft"
