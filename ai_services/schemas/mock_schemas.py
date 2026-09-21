from enum import Enum
from pydantic import BaseModel, Field, model_validator
from .analyzer_schemas import DifficultyTag

class MockMode(str, Enum):
    exam_replica = "exam_replica"
    diagnostic_drill = "diagnostic_drill"

class MockGeneratorInput(BaseModel):
    mode: MockMode
    target_node_ids: list[str]
    source_pyq_refs: list[str]
    node_weights: dict[str, float]
    weakness_scores: dict[str, float] = Field(default_factory=dict)
    question_count: int = Field(ge=1, le=100)
    time_limit_minutes: int = Field(ge=1)

    @model_validator(mode="after")
    def require_nodes(self):
        if not self.target_node_ids:
            raise ValueError("target_node_ids must contain at least one node")
        targets = set(self.target_node_ids)
        invalid_weights = set(self.node_weights) - targets
        missing_weights = targets - set(self.node_weights)
        if invalid_weights or missing_weights or any(weight < 0 for weight in self.node_weights.values()):
            raise ValueError("node_weights must be non-negative and include every target_node_id")
        if not any(weight > 0 for weight in self.node_weights.values()):
            raise ValueError("node_weights must contain at least one positive evidence-derived weight")
        invalid_weaknesses = set(self.weakness_scores) - targets
        if invalid_weaknesses or any(not 0 <= score <= 1 for score in self.weakness_scores.values()):
            raise ValueError("weakness_scores must be between 0 and 1 and reference target_node_ids only")
        if self.mode == MockMode.diagnostic_drill and targets - set(self.weakness_scores):
            raise ValueError("diagnostic_drill requires a weakness score for every target_node_id")
        return self

class MockQuestion(BaseModel):
    question_id: str
    node_id: str
    source_pyq_dna: str
    question_text: str
    options: list[str] = Field(min_length=2, max_length=4)
    correct_option_index: int = Field(ge=0)
    marks: float
    negative_marks: float
    difficulty_tag: DifficultyTag
    explanation: str

    @model_validator(mode="after")
    def validate_answer(self):
        if len(self.options) != 4:
            raise ValueError("each mock question must contain exactly four options")
        if self.correct_option_index >= len(self.options):
            raise ValueError("correct_option_index must point to an option")
        if self.marks <= 0 or self.negative_marks < 0:
            raise ValueError("marks must be positive and negative_marks cannot be negative")
        return self

class MockTest(BaseModel):
    test_id: str
    mode: MockMode
    questions: list[MockQuestion]
    total_marks: float
    time_limit_minutes: int

class QuestionResult(BaseModel):
    question_id: str
    node_id: str
    time_spent_s: int = Field(ge=0)
    answer_changes_count: int = Field(ge=0)
    flagged_for_review: bool
    final_answer_index: int = Field(ge=-1)
    is_correct: bool

class MockSubmission(BaseModel):
    test_id: str
    user_id: str
    per_question_results: list[QuestionResult]
    total_time_s: int = Field(ge=0)
