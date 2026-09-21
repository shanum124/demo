from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field
from .mock_schemas import QuestionResult

class IntentClass(str, Enum):
    chat_qa = "chat_qa"
    doubt_solve = "doubt_solve"
    mock_request = "mock_request"
    report_query = "report_query"

class EpisodicTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    ts: datetime

class PacingProfile(BaseModel):
    avg_seconds_per_question: float = 0
    tendency: Literal["rushed", "balanced", "deliberate"] = "balanced"

class WeaknessEntry(BaseModel):
    node_id: str
    confidence: float = Field(ge=0, le=1)
    last_seen: datetime

class MasteryEntry(BaseModel):
    node_id: str
    confidence: float = Field(ge=0, le=1)
    last_verified: datetime

class SemanticProfile(BaseModel):
    user_id: str
    exam_name: str = ""
    current_weaknesses: list[WeaknessEntry] = Field(default_factory=list)
    mastered_topics: list[MasteryEntry] = Field(default_factory=list)
    pacing_profile: PacingProfile = Field(default_factory=PacingProfile)
    preferred_learning_style: Literal["visual", "code_first", "socratic", "exam_drill_heavy"] = "socratic"
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    profile_version: int = 1

class OrchestratorInput(BaseModel):
    user_id: str
    exam_id: str | None = None
    user_message: str
    episodic_window: list[EpisodicTurn]
    semantic_profile: SemanticProfile
    custom_instructions: list[str] = Field(default_factory=list)

class ActionBlock(BaseModel):
    tool_call: str | None = None
    tool_args: dict | None = None
    spawn_thread: bool = False
    new_thread_id: str | None = None

class ProfileDelta(BaseModel):
    current_weaknesses_add: list[str] = Field(default_factory=list)
    current_weaknesses_remove: list[str] = Field(default_factory=list)
    mastered_topics_add: list[str] = Field(default_factory=list)

class OrchestratorOutput(BaseModel):
    intent_class: str
    action: ActionBlock = Field(default_factory=ActionBlock)
    assistant_response: str
    profile_delta: ProfileDelta = Field(default_factory=ProfileDelta)
