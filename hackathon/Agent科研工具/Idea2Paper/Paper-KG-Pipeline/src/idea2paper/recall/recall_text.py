def build_recall_idea_text(idea: dict) -> str:
    return (idea.get("description") or "")


def build_recall_paper_text(paper: dict) -> str:
    return (paper.get("title") or "")


def truncate_for_embedding(text: str, max_len: int = 2000) -> str:
    if not text:
        return ""
    return text[:max_len]
