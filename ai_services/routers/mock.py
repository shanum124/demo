from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ai_services.schemas.mock_schemas import *
from ai_services.schemas.mcp_schemas import TelemetryEvent
from datetime import datetime, timezone
from ai_services.agents.agent4_mock_generator import MockGenerationError
router = APIRouter()
class GenerateRequest(BaseModel):
    user_id: str
    mode: MockMode
    question_count: int = Field(ge=1, le=100)
    time_limit_minutes: int = Field(ge=1)
    target_node_ids: list[str] = Field(min_length=1)
    source_pyq_refs: list[str] = Field(default_factory=list)
    node_weights: dict[str, float]
    weakness_scores: dict[str, float] = Field(default_factory=dict)

def configure(generator, bridge, extractor):
    @router.post("/mock/generate")
    async def generate(request: GenerateRequest):
        try:
            extracted = await extractor.extract_mock(MockGeneratorInput(
                mode=request.mode,
                target_node_ids=request.target_node_ids,
                source_pyq_refs=request.source_pyq_refs,
                node_weights=request.node_weights,
                weakness_scores=request.weakness_scores,
                question_count=request.question_count,
                time_limit_minutes=request.time_limit_minutes,
            ))
            test = await generator.run(extracted.mock_input)
        except MockGenerationError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"reason": exc.reason, "message": str(exc)}) from exc
        return test
    @router.post("/mock/submit")
    async def submit(submission: MockSubmission):
        test = bridge.mocks.get(submission.test_id)
        if not test: raise HTTPException(404, "test not found")
        score = sum(q.marks for q, r in [(q, next((x for x in submission.per_question_results if x.question_id == q.question_id), None)) for q in test.questions] if r and r.final_answer_index == q.correct_option_index)
        await bridge.telemetry_log_event(TelemetryEvent(event_type="mock_completed", payload={"results": [r.model_dump() for r in submission.per_question_results]}, ts=datetime.now(timezone.utc), user_id=submission.user_id))
        return {"score": score, "test_id": submission.test_id}
    return router
