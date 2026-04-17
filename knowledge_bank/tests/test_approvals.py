from __future__ import annotations

from tests.conftest import create_knowledge


def test_approve_one_draft_unit(client, source_factory, compiled_units_payload):
    source = source_factory("week3_entropy_notes.pdf", b"%PDF-1.4\nstub", "application/pdf")
    compile_result = create_knowledge(client, source["source_id"], compiled_units_payload)
    knowledge_id = compile_result["created_knowledge_ids"][0]

    response = client.post(
        f"/approvals/{knowledge_id}",
        json={
            "target_status": "approved",
            "reviewer": "Professor Yang Long",
            "decision_reason": "Aligned with syllabus",
        },
    )
    assert response.status_code == 200
    approval = response.json()
    assert approval["knowledge_id"] == knowledge_id
    assert approval["new_status"] == "approved"


def test_bulk_approve_by_topic_phrase(client, source_factory):
    source = source_factory("linear_regression_notes.txt", b"linear regression notes", "text/plain")
    compile_result = create_knowledge(
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

    response = client.post(
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
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["approved_count"] == 2

    approved_ids = set(payload["approved_knowledge_ids"])
    assert compile_result["created_knowledge_ids"][0] in approved_ids
    assert compile_result["created_knowledge_ids"][1] in approved_ids
    assert compile_result["created_knowledge_ids"][2] not in approved_ids
