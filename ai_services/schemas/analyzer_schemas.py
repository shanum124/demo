from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field

class DifficultyTag(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"

class SyllabusNode(BaseModel):
    node_id: str
    title: str
    parent_id: str | None = None
    node_type: str = "topic"

class PYQIndexItem(BaseModel):
    pyq_id: str
    node_ids: list[str]
    year: int | None = None
    marks: float | None = Field(default=None, gt=0)
    difficulty_tag: DifficultyTag | None = None
    question_type: str | None = None
    question_number: str | None = None
    source_document: str | None = None
    dna_tags: list[str] = Field(default_factory=list)

class NotesCoverageItem(BaseModel):
    node_id: str
    chunk_ids: list[str]
    coverage_score: float = Field(ge=0, le=1)

class AnalyzerInput(BaseModel):
    exam_name: str
    exam_timing_weeks: int
    exam_id: str | None = None
    syllabus_nodes: list[SyllabusNode]
    pyq_index: list[PYQIndexItem]
    notes_coverage_map: list[NotesCoverageItem]

class NodeScore(BaseModel):
    node_id: str
    weightage_pct: float
    questions_asked: int
    papers_appeared: int
    years_appeared: list[int]
    frequency_last_5yr: float = Field(ge=0, le=1)
    avg_marks: float
    difficulty_index: float
    notes_coverage_score: float
    roi_score: float
    gap_flag: bool
    source_pyq_ids: list[str]

class AnalyzerOutput(BaseModel):
    analysis_id: str = Field(default_factory=lambda: "analysis-unknown")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    node_scores: list[NodeScore]
    top_roi_nodes: list[str]
    critical_gaps: list[str]
    reasoning_trace: str
    analysis_status: Literal["success", "deterministic_fallback", "failed"] = "success"
    failure_reason: str | None = None
