def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return text.lower().split()


def to_token_set(text: str) -> frozenset:
    return frozenset(tokenize(text))


def jaccard_from_sets(tokens1: frozenset, tokens2: frozenset) -> float:
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(intersection) / len(union)
