from __future__ import annotations


def test_store_cohort_signal(client):
    response = client.post(
        "/signals/cohort",
        json={
            "tested_deck_id": "deck_ml_week3_v1",
            "related_knowledge_ids": ["kb_014"],
            "weak_topics": ["entropy intuition"],
            "repeated_confusion_points": ["why lower entropy is better"],
            "misconception_clusters": ["entropy equals randomness only"],
            "evidence_refs": ["run_001", "run_002"],
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["signal_id"].startswith("sig_")
    assert payload["status"] == "stored"
