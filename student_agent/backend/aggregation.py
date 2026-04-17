from __future__ import annotations

from collections import Counter, defaultdict

from backend.models import (
    AggregatedSignal,
    CountItem,
    EvidenceRef,
    GovernanceTrace,
    LectureDeck,
    ProfileName,
    ProfileTagCount,
    RevisionTarget,
    RunEvidenceSnippet,
    SlideIssueCount,
)
from backend.storage import DECK_STORE, RUN_STORE, SIGNAL_STORE


def _counter_to_items(counter: Counter[str]) -> list[CountItem]:
    return [CountItem(label=label, count=count) for label, count in counter.most_common()]


def _profile_counter_to_items(
    profile_counters: dict[ProfileName, Counter[str]],
) -> list[ProfileTagCount]:
    items: list[ProfileTagCount] = []
    for profile_name, counter in profile_counters.items():
        for tag, count in counter.most_common():
            items.append(ProfileTagCount(profile_name=profile_name, tag=tag, count=count))
    return items


def _top_labels(counter: Counter[str], prefix: str, limit: int = 5) -> list[str]:
    return [f"{label} ({count})" for label, count in counter.most_common(limit) if label != prefix]


def _truncate(text: str, limit: int = 300) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def aggregate_runs_for_deck(deck_id: str) -> AggregatedSignal:
    deck: LectureDeck = DECK_STORE[deck_id]
    runs = [run for run in RUN_STORE.values() if run.deck_id == deck_id and run.answer]

    confusion_counts: Counter[str] = Counter()
    prerequisite_counts: Counter[str] = Counter()
    misconception_counts: Counter[str] = Counter()
    weak_topic_counts: Counter[str] = Counter()
    slide_counts: Counter[str] = Counter()

    confusion_by_profile: dict[ProfileName, Counter[str]] = defaultdict(Counter)
    prerequisite_by_profile: dict[ProfileName, Counter[str]] = defaultdict(Counter)
    misconception_by_profile: dict[ProfileName, Counter[str]] = defaultdict(Counter)

    slide_title_map = {slide.slide_id: slide.title for slide in deck.slides}
    profile_evidence: dict[ProfileName, tuple[int, RunEvidenceSnippet]] = {}
    revision_targets: list[RevisionTarget] = []
    evidence_refs: list[EvidenceRef] = []

    for run in runs:
        answer = run.answer
        if not answer:
            continue

        confusion_counts.update(answer.confusion_tags)
        prerequisite_counts.update(answer.missed_prerequisites)
        misconception_counts.update(answer.misconception_flags)
        confusion_by_profile[run.student_profile].update(answer.confusion_tags)
        prerequisite_by_profile[run.student_profile].update(answer.missed_prerequisites)
        misconception_by_profile[run.student_profile].update(answer.misconception_flags)
        evidence_refs.extend(run.evidence_refs or [
            EvidenceRef(
                run_id=run.run_id,
                slide_refs=answer.evidence_slide_refs or run.slide_refs,
                task_type=run.task_type,
                student_profile=run.student_profile,
            )
        ])

        if run.student_profile == ProfileName.weak:
            weak_topic_counts.update(answer.confusion_tags)
            weak_topic_counts.update(answer.missed_prerequisites)

        for slide_ref in answer.evidence_slide_refs or run.slide_refs:
            slide_counts[slide_ref] += 1

        signal_strength = (
            len(answer.confusion_tags)
            + len(answer.missed_prerequisites)
            + len(answer.misconception_flags)
        )
        snippet = RunEvidenceSnippet(
            run_id=run.run_id,
            student_profile=run.student_profile,
            task_type=run.task_type,
            main_answer=_truncate(answer.main_answer),
            evidence_slide_refs=answer.evidence_slide_refs,
        )
        snippet_score = _evidence_score(signal_strength, snippet)
        current = profile_evidence.get(run.student_profile)
        if current is None or snippet_score > current[0]:
            profile_evidence[run.student_profile] = (snippet_score, snippet)

    slide_issue_counts = [
        SlideIssueCount(
            slide_id=slide_id,
            slide_title=slide_title_map.get(slide_id, slide_id),
            count=count,
        )
        for slide_id, count in slide_counts.most_common()
    ]

    for slide_issue in slide_issue_counts[:5]:
        affected_profiles = [
            profile_name
            for profile_name in confusion_by_profile
            if any(slide_issue.slide_id in (run.answer.evidence_slide_refs if run.answer else []) for run in runs if run.student_profile == profile_name)
        ]
        revision_targets.append(
            RevisionTarget(
                priority=slide_issue.count,
                target_type="slide",
                target_ref=slide_issue.slide_id,
                issue_types=_issue_types_for_slide(slide_issue.slide_id, runs),
                affected_profiles=affected_profiles,
                reason=f"Slide {slide_issue.slide_title} appears in {slide_issue.count} issue-linked run(s).",
                suggestion=f"Clarify {slide_issue.slide_title} with prerequisite reminders, tighter definitions, and at least one worked example.",
            )
        )

    summary = AggregatedSignal(
        signal_id=f"signal_{deck_id}",
        tested_deck_id=deck_id,
        weak_topics=_top_labels(weak_topic_counts, prefix=""),
        repeated_confusion_points=_top_labels(confusion_counts, prefix=""),
        misconception_clusters=_top_labels(misconception_counts, prefix=""),
        missing_prerequisite_patterns=_top_labels(prerequisite_counts, prefix=""),
        recommended_revision_targets=[
            f"[P{target.priority}] {target.target_type}:{target.target_ref} - {target.reason}"
            for target in revision_targets
        ],
        weak_topic_counts=_counter_to_items(weak_topic_counts),
        confusion_tag_counts=_counter_to_items(confusion_counts),
        prerequisite_tag_counts=_counter_to_items(prerequisite_counts),
        misconception_tag_counts=_counter_to_items(misconception_counts),
        confusion_by_profile=_profile_counter_to_items(confusion_by_profile),
        prerequisite_by_profile=_profile_counter_to_items(prerequisite_by_profile),
        misconception_by_profile=_profile_counter_to_items(misconception_by_profile),
        slide_issue_counts=slide_issue_counts,
        representative_evidence=[item[1] for item in profile_evidence.values()],
        evidence_refs=evidence_refs,
        run_ids=[run.run_id for run in runs],
        revision_targets=revision_targets,
        governance_trace=GovernanceTrace(
            signal_id=f"signal_{deck_id}",
            tested_deck_id=deck_id,
            run_ids=[run.run_id for run in runs],
            evidence_refs=evidence_refs,
            slide_ids=[item.slide_id for item in slide_issue_counts],
        ),
    )
    SIGNAL_STORE[deck_id] = summary
    return summary


def _evidence_score(signal_strength: int, snippet: RunEvidenceSnippet) -> int:
    return signal_strength * 100 + len(snippet.main_answer) + len(snippet.evidence_slide_refs) * 20


def _issue_types_for_slide(slide_id: str, runs: list) -> list[str]:
    issue_types: set[str] = set()
    for run in runs:
        answer = run.answer
        if not answer or slide_id not in answer.evidence_slide_refs:
            continue
        if answer.confusion_tags:
            issue_types.add("confusion")
        if answer.missed_prerequisites:
            issue_types.add("prerequisite")
        if answer.misconception_flags:
            issue_types.add("misconception")
    return sorted(issue_types)
