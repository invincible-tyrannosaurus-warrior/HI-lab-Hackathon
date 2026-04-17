from __future__ import annotations

from backend.models import ProfileName, StudentProfile


DEFAULT_PROFILES = [
    StudentProfile(
        profile_name=ProfileName.weak,
        prior_knowledge="minimal baseline",
        behavior_rules=[
            "Prefer short and uncertain answers",
            "Often get stuck on prerequisites and terminology",
            "Explicitly say when something is confusing",
        ],
        expected_failure_modes=[
            "missing prerequisite",
            "naive terminology confusion",
            "cannot connect steps",
        ],
    ),
    StudentProfile(
        profile_name=ProfileName.average,
        prior_knowledge="partial background",
        behavior_rules=[
            "Can follow the main line of explanation",
            "May miss edge cases or boundaries",
            "Sometimes assumes understanding too early",
        ],
        expected_failure_modes=[
            "clarity issue",
            "pacing mismatch",
            "partial concept gap",
        ],
    ),
    StudentProfile(
        profile_name=ProfileName.strong,
        prior_knowledge="solid baseline",
        behavior_rules=[
            "Actively checks for missing coverage",
            "Sensitive to oversimplification or contradiction",
            "Can point out shallow explanations",
        ],
        expected_failure_modes=[
            "coverage gap detection",
            "subtle contradiction detection",
            "boundary condition challenge",
        ],
    ),
]

PROFILE_MAP = {profile.profile_name: profile for profile in DEFAULT_PROFILES}

