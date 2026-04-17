from __future__ import annotations

import re


def normalize_topic_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", normalized)


def topic_tokens(value: str | None) -> set[str]:
    normalized = normalize_topic_text(value)
    return {token for token in normalized.split(" ") if token}


def topic_match_score(topic_query: str | None, candidate_values: list[str]) -> int | None:
    normalized_query = normalize_topic_text(topic_query)
    if not normalized_query:
        return 0

    query_tokens = topic_tokens(normalized_query)
    best_score: int | None = None
    for candidate in candidate_values:
        normalized_candidate = normalize_topic_text(candidate)
        if not normalized_candidate:
            continue

        candidate_tokens = topic_tokens(normalized_candidate)
        score: int | None = None
        if normalized_candidate == normalized_query:
            score = 0
        elif normalized_query in normalized_candidate:
            score = 1
        elif query_tokens and query_tokens.issubset(candidate_tokens):
            score = 2

        if score is None:
            continue
        if best_score is None or score < best_score:
            best_score = score
    return best_score


def matches_topic_scope(topic_scope: list[str], candidate_values: list[str]) -> bool:
    if not topic_scope:
        return True
    return any(topic_match_score(topic, candidate_values) is not None for topic in topic_scope)


def best_topic_scope_score(topic_scope: list[str], candidate_values: list[str]) -> int | None:
    scores = [
        topic_match_score(topic, candidate_values)
        for topic in topic_scope
        if topic_match_score(topic, candidate_values) is not None
    ]
    if not scores:
        return None
    return min(scores)
