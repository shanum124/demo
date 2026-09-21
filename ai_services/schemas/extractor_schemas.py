from typing import Literal

from pydantic import BaseModel, Field

from .analyzer_schemas import AnalyzerInput
from .mock_schemas import MockGeneratorInput
from .orchestrator_schemas import OrchestratorInput


class ExtractorMetadata(BaseModel):
    mode: Literal["deterministic", "llm_assisted"] = "deterministic"


class InstructionExtraction(BaseModel):
    instructions: list[str] = Field(default_factory=list, max_length=8)


class ExtractedIngestionRequest(BaseModel):
    exam_name: str = Field(min_length=1, max_length=200)
    exam_timing_weeks: int = Field(ge=1, le=520)
    custom_instructions: list[str] = Field(default_factory=list, max_length=8)
    metadata: ExtractorMetadata = Field(default_factory=ExtractorMetadata)


class ExtractedIngestionInput(BaseModel):
    analyzer_input: AnalyzerInput
    custom_instructions: list[str] = Field(default_factory=list, max_length=8)
    metadata: ExtractorMetadata = Field(default_factory=ExtractorMetadata)


class ExtractedStrategyInput(BaseModel):
    analyzer_input: AnalyzerInput
    custom_instructions: list[str] = Field(default_factory=list, max_length=8)
    doc_id: str
    metadata: ExtractorMetadata = Field(default_factory=ExtractorMetadata)


class ExtractedChatInput(BaseModel):
    orchestrator_input: OrchestratorInput
    metadata: ExtractorMetadata = Field(default_factory=ExtractorMetadata)


class ExtractedMockInput(BaseModel):
    mock_input: MockGeneratorInput
    metadata: ExtractorMetadata = Field(default_factory=ExtractorMetadata)