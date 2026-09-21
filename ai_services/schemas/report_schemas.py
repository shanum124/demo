from typing import Literal
from pydantic import BaseModel, Field
from .analyzer_schemas import AnalyzerOutput

class ReportGeneratorInput(BaseModel):
    analyzer_output: AnalyzerOutput
    exam_timing_weeks: int
    custom_instructions: list[str] = Field(default_factory=list)

class ReportDraft(BaseModel):
    report_draft_id: str
    markdown_body: str = Field(min_length=1)
    phase_count: int
    referenced_node_ids: list[str]
    generation_status: Literal["success", "deterministic_fallback", "failed"]
    failure_reason: str | None

class ValidationReport(BaseModel):
    claims_checked: int
    claims_removed: int
    formatting_fixes: int
    hallucination_flags: list[str]

class NodeScoreLookup(BaseModel):
    node_id: str
    roi_score: float
    weightage_pct: float

class EditorInput(BaseModel):
    markdown_body: str
    analyzer_output_ref: str
    node_scores_lookup: list[NodeScoreLookup]
    expected_phase_count: int = 3
    doc_id: str = "strategy"

class EditorOutput(BaseModel):
    validated_markdown: str = Field(min_length=1)
    validation_report: ValidationReport
    status: Literal["approved", "revised", "rejected"]
    generation_status: Literal["success", "deterministic_fallback", "failed"]
    failure_reason: str | None
