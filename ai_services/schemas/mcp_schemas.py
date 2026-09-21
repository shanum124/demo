from datetime import datetime
from pydantic import BaseModel, Field

class VectorSearchRequest(BaseModel):
    query: str
    node_id_filter: list[str] | None = None
    exam_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=5)

class VectorSearchResult(BaseModel):
    chunk_id: str
    score: float
    snippet: str = Field(max_length=500)
    node_id: str
    source_doc_id: str = ""
    page: int | None = None
    section: str | None = None

class MarkdownWriteRequest(BaseModel):
    doc_id: str
    section: str
    patch: str = Field(max_length=50_000)

class MarkdownWriteResult(BaseModel):
    success: bool
    version: int

class TelemetryEvent(BaseModel):
    event_type: str
    payload: dict
    ts: datetime
    user_id: str

class TelemetryResult(BaseModel):
    logged: bool
    profile_updated: bool

class PYQFetchRequest(BaseModel):
    pyq_ids: list[str]
    fields: list[str] | None = None

class NodeGraphQueryRequest(BaseModel):
    node_id: str | None = None
    depth: int = Field(default=2, ge=0, le=5)
