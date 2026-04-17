from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SlideBlock(BaseModel):
    slide_id: str
    title: str
    key_points: list[str] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    raw_text: Optional[str] = None


class LectureDeck(BaseModel):
    deck_id: str
    module_tag: str
    week_tag: str
    topic_tags: list[str] = Field(default_factory=list)
    slides: list[SlideBlock]


class PPTXIngestRequest(BaseModel):
    pptx_path: str
    deck_id: str
    module_tag: str
    week_tag: str
    topic_tags: list[str] = Field(default_factory=list)


class ProfileName(str, Enum):
    weak = "weak"
    average = "average"
    strong = "strong"


class StudentProfile(BaseModel):
    profile_name: ProfileName
    prior_knowledge: str
    behavior_rules: list[str]
    expected_failure_modes: list[str] = Field(default_factory=list)


class TaskType(str, Enum):
    explain_back = "explain_back"
    short_qa = "short_qa"
    confusion_report = "confusion_report"
    coverage_check = "coverage_check"


class EvaluationTask(BaseModel):
    task_type: TaskType
    instruction: str
    question_set: list[str] = Field(default_factory=list)
    output_format_hint: Optional[str] = None


class RunAnswer(BaseModel):
    main_answer: str
    confidence: Optional[float] = None
    confusion_tags: list[str] = Field(default_factory=list)
    missed_prerequisites: list[str] = Field(default_factory=list)
    misconception_flags: list[str] = Field(default_factory=list)
    evidence_slide_refs: list[str] = Field(default_factory=list)


class EvidenceRef(BaseModel):
    run_id: str
    slide_refs: list[str] = Field(default_factory=list)
    task_type: Optional[TaskType] = None
    student_profile: Optional[ProfileName] = None


class QAQuestion(BaseModel):
    question_id: str
    prompt: str
    correct_answer: str
    slide_refs: list[str] = Field(default_factory=list)
    concept_tags: list[str] = Field(default_factory=list)


class QAAnswerRecord(BaseModel):
    question_id: str
    prompt: str
    student_answer: str
    correct_answer: str
    is_correct: bool
    confidence: float = 0.0
    missed_concepts: list[str] = Field(default_factory=list)
    evidence_slide_refs: list[str] = Field(default_factory=list)


class QAPassResult(BaseModel):
    stage: str
    correct_count: int
    total_questions: int
    accuracy: float
    answers: list[QAAnswerRecord] = Field(default_factory=list)


class HandoffItem(BaseModel):
    priority: str = "high"
    target_type: str = "question"
    target_ref: str
    issue_types: list[str] = Field(default_factory=list)
    affected_profiles: list[ProfileName] = Field(default_factory=list)
    reason: str
    suggestion: str
    question_id: str
    prompt: str
    student_answer: str = ""
    correct_answer: str = ""
    failure_reason: str
    missed_concepts: list[str] = Field(default_factory=list)
    recommended_followup: str
    slide_refs: list[str] = Field(default_factory=list)


class CollaboratorHandoff(BaseModel):
    handoff_id: str
    schema_version: str = "collaborator_handoff.v1"
    handoff_type: str = "content_revision_handoff"
    deck_id: str
    benchmark_id: Optional[str] = None
    source_stage: str = "after_pass"
    source_system: str = "student_agent_testing"
    target_collaborator: str = "content_revision_collaborator"
    unresolved_count: int
    items: list[HandoffItem] = Field(default_factory=list)


class QAImprovementResult(BaseModel):
    benchmark_id: str
    deck_id: str
    profile_name: ProfileName
    total_questions: int
    model_used: str
    before_pass: QAPassResult
    after_pass: QAPassResult
    improvement_delta: int
    collaborator_handoff: CollaboratorHandoff


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class EvaluationRun(BaseModel):
    run_id: str
    deck_id: str
    slide_refs: list[str]
    student_profile: ProfileName
    task_type: TaskType
    status: RunStatus
    answer: Optional[RunAnswer] = None
    answer_text: str = ""
    confusion_tags: list[str] = Field(default_factory=list)
    missed_prerequisites: list[str] = Field(default_factory=list)
    misconception_flags: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    error_message: Optional[str] = None


class CountItem(BaseModel):
    label: str
    count: int


class ProfileTagCount(BaseModel):
    profile_name: ProfileName
    tag: str
    count: int


class SlideIssueCount(BaseModel):
    slide_id: str
    slide_title: str
    count: int


class RunEvidenceSnippet(BaseModel):
    run_id: str
    student_profile: ProfileName
    task_type: TaskType
    main_answer: str
    evidence_slide_refs: list[str] = Field(default_factory=list)


class GovernanceTrace(BaseModel):
    signal_id: str
    tested_deck_id: str
    run_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    slide_ids: list[str] = Field(default_factory=list)


class RevisionTarget(BaseModel):
    priority: int
    target_type: str
    target_ref: str
    issue_types: list[str] = Field(default_factory=list)
    affected_profiles: list[ProfileName] = Field(default_factory=list)
    reason: str
    suggestion: str


class AggregatedSignal(BaseModel):
    signal_id: str
    tested_deck_id: str
    weak_topics: list[str] = Field(default_factory=list)
    repeated_confusion_points: list[str] = Field(default_factory=list)
    misconception_clusters: list[str] = Field(default_factory=list)
    missing_prerequisite_patterns: list[str] = Field(default_factory=list)
    recommended_revision_targets: list[str] = Field(default_factory=list)
    weak_topic_counts: list[CountItem] = Field(default_factory=list)
    confusion_tag_counts: list[CountItem] = Field(default_factory=list)
    prerequisite_tag_counts: list[CountItem] = Field(default_factory=list)
    misconception_tag_counts: list[CountItem] = Field(default_factory=list)
    confusion_by_profile: list[ProfileTagCount] = Field(default_factory=list)
    prerequisite_by_profile: list[ProfileTagCount] = Field(default_factory=list)
    misconception_by_profile: list[ProfileTagCount] = Field(default_factory=list)
    slide_issue_counts: list[SlideIssueCount] = Field(default_factory=list)
    representative_evidence: list[RunEvidenceSnippet] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    revision_targets: list[RevisionTarget] = Field(default_factory=list)
    governance_trace: Optional[GovernanceTrace] = None


class EvaluationJob(BaseModel):
    job_id: str
    deck_id: str
    profile_names: list[ProfileName]
    task_types: list[TaskType]
    status: RunStatus
    run_ids: list[str] = Field(default_factory=list)
    summary_ready: bool = False


class RunEvaluationRequest(BaseModel):
    deck: LectureDeck
    profile_names: list[ProfileName] = Field(
        default_factory=lambda: [ProfileName.weak, ProfileName.average, ProfileName.strong]
    )
    task_types: list[TaskType] = Field(
        default_factory=lambda: [
            TaskType.explain_back,
            TaskType.short_qa,
            TaskType.confusion_report,
            TaskType.coverage_check,
        ]
    )
    auto_aggregate: bool = True
    use_mock: bool = True


class QABenchmarkRequest(BaseModel):
    deck: LectureDeck
    questions: list[QAQuestion]
    profile_name: ProfileName = ProfileName.average
    qa_support_content: list[str] = Field(default_factory=list)
    target_collaborator: str = "next_collaborator"
    llm_model: str = "qwen/qwen-2.5-7b-instruct"
    provider_order: list[str] = Field(default_factory=list)
    allow_fallbacks: bool = True
    use_mock: bool = True
