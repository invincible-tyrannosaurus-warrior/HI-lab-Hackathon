from __future__ import annotations

from pathlib import Path

from tests.conftest import create_knowledge


def test_search_knowledge_by_module_topic_and_status(client, source_factory, compiled_units_payload):
    source = source_factory("week3_entropy_notes.pdf", b"%PDF-1.4\nstub", "application/pdf")
    create_knowledge(client, source["source_id"], compiled_units_payload)

    response = client.get(
        "/knowledge/search",
        params={"module": "Machine Learning", "topic": "entropy", "approval_status": "draft"},
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    assert all(item["approval_status"] == "draft" for item in results)


def test_context_bundle_returns_approved_only(client, source_factory, compiled_units_payload):
    source = source_factory("week3_entropy_notes.pdf", b"%PDF-1.4\nstub", "application/pdf")
    compile_result = create_knowledge(client, source["source_id"], compiled_units_payload)
    first_id = compile_result["created_knowledge_ids"][0]

    approval_response = client.post(
        f"/approvals/{first_id}",
        json={
            "target_status": "approved",
            "reviewer": "Professor Yang Long",
            "decision_reason": "Aligned with syllabus",
        },
    )
    assert approval_response.status_code == 200

    response = client.get(
        "/knowledge/context-bundle",
        params={
            "module": "Machine Learning",
            "week": "week_03",
            "topic": "entropy",
            "generation_target": "lecture_slide",
        },
    )
    assert response.status_code == 200
    bundle = response.json()["approved_context_bundle"]
    assert len(bundle) == 1
    assert bundle[0]["knowledge_id"] == first_id
    assert bundle[0]["approval_status"] == "approved"
    assert "body_text" in bundle[0]
    assert response.json()["source_registry_refs"][0]["source_id"] == source["source_id"]
    assert "retrieval_trace" in response.json()


def test_context_bundle_includes_supporting_source_chunks_for_text_source(client, source_factory, compiled_units_payload):
    source = source_factory(
        "week3_entropy_notes.txt",
        b"Entropy measures uncertainty. Information gain compares parent entropy and child entropy in decision trees.",
        "text/plain",
    )
    compile_result = create_knowledge(client, source["source_id"], compiled_units_payload)
    first_id = compile_result["created_knowledge_ids"][0]

    approval_response = client.post(
        f"/approvals/{first_id}",
        json={
            "target_status": "approved",
            "reviewer": "Professor Yang Long",
            "decision_reason": "Aligned with syllabus",
        },
    )
    assert approval_response.status_code == 200

    response = client.get(
        "/knowledge/context-bundle",
        params={
            "module": "Machine Learning",
            "week": "week_03",
            "topic": "entropy",
            "generation_target": "pptx",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["supporting_source_chunks"]
    assert payload["supporting_source_chunks"][0]["source_id"] == source["source_id"]
    assert payload["retrieval_trace"]["vector_search_used"] is True
    assert "source_chunks" in payload["retrieval_trace"]["vector_collections_queried"]


def test_text_source_chunking_persists_manifests(client, source_factory, compiled_units_payload):
    source = source_factory(
        "week3_entropy_notes.txt",
        b"Entropy measures uncertainty. " * 200,
        "text/plain",
    )
    create_knowledge(client, source["source_id"], compiled_units_payload)

    processed_dir = Path(client.app.root_path or ".")  # not used, just keeps local scope simple
    del processed_dir

    from backend.config import get_processed_storage_root

    source_dir = get_processed_storage_root() / source["source_id"]
    assert (source_dir / "chunk_manifest.jsonl").exists()
    assert (source_dir / "chunking_summary.json").exists()


def test_summary_endpoint_returns_counts(client, source_factory, compiled_units_payload):
    source = source_factory("week3_entropy_notes.pdf", b"%PDF-1.4\nstub", "application/pdf")
    compile_result = create_knowledge(client, source["source_id"], compiled_units_payload)

    client.post(
        f"/approvals/{compile_result['created_knowledge_ids'][0]}",
        json={
            "target_status": "approved",
            "reviewer": "Professor Yang Long",
            "decision_reason": "Aligned with syllabus",
        },
    )

    response = client.get("/knowledge/summary")
    assert response.status_code == 200
    summary = response.json()
    assert summary["registered_sources"] == 1
    assert summary["draft_units"] == 1
    assert summary["approved_units"] == 1
    assert summary["latest_update_at"] is not None


def test_graph_endpoint_returns_nodes_and_edges(client, source_factory, compiled_units_payload):
    source = source_factory("week3_entropy_notes.pdf", b"%PDF-1.4\nstub", "application/pdf")
    compile_result = create_knowledge(client, source["source_id"], compiled_units_payload)

    response = client.get("/knowledge/graph")
    assert response.status_code == 200
    graph = response.json()
    node_ids = {node["id"] for node in graph["nodes"]}
    assert source["source_id"] in node_ids
    assert compile_result["created_knowledge_ids"][0] in node_ids
    assert any(edge["type"] == "derived_from" for edge in graph["edges"])


def test_topic_phrase_bundle_returns_only_relevant_approved_units(client, source_factory):
    source = source_factory("linear_regression_notes.txt", b"linear regression notes", "text/plain")
    create_knowledge(
        client,
        source["source_id"],
        [
            {
                "title": "Simple linear regression",
                "summary": "Intro to linear regression.",
                "body_text": "Linear regression models a continuous target with a linear function.",
                "topic_tags": ["simple_linear_regression"],
                "difficulty_level": "intro_undergrad",
                "pedagogical_role": "concept",
                "prerequisite_links": [],
                "learning_outcome_links": [],
            },
            {
                "title": "Multiple linear regression",
                "summary": "Generalize simple linear regression to multiple inputs.",
                "body_text": "Multiple linear regression extends the model to multiple explanatory variables.",
                "topic_tags": ["multiple_linear_regression"],
                "difficulty_level": "intro_undergrad",
                "pedagogical_role": "concept",
                "prerequisite_links": [],
                "learning_outcome_links": [],
            },
            {
                "title": "Regression with KNN",
                "summary": "A different regression family.",
                "body_text": "KNN regression predicts by averaging nearby labels.",
                "topic_tags": ["regression_with_knn"],
                "difficulty_level": "intro_undergrad",
                "pedagogical_role": "example",
                "prerequisite_links": [],
                "learning_outcome_links": [],
            },
        ],
    )

    bulk_approval = client.post(
        "/approvals/bulk",
        json={
            "target_status": "approved",
            "reviewer": "Professor Yang Long",
            "decision_reason": "Approve linear regression bundle candidates",
            "module": "Machine Learning",
            "week": "week_03",
            "topic": "linear regression",
        },
    )
    assert bulk_approval.status_code == 200, bulk_approval.text

    search_response = client.get(
        "/knowledge/search",
        params={
            "module": "Machine Learning",
            "week": "week_03",
            "topic": "linear regression",
        },
    )
    assert search_response.status_code == 200
    search_titles = [item["title"] for item in search_response.json()]
    assert "Simple linear regression" in search_titles
    assert "Multiple linear regression" in search_titles
    assert "Regression with KNN" not in search_titles

    response = client.get(
        "/knowledge/context-bundle",
        params={
            "module": "Machine Learning",
            "week": "week_03",
            "topic": "linear regression",
            "generation_target": "pptx",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    titles = [item["title"] for item in payload["approved_context_bundle"]]
    assert "Simple linear regression" in titles
    assert "Multiple linear regression" in titles
    assert "Regression with KNN" not in titles
