from uuid import uuid4
from fastapi import APIRouter
from pydantic import BaseModel, Field
from ai_services.memory.episodic_memory import EpisodicMemory
from ai_services.schemas.orchestrator_schemas import OrchestratorInput
router = APIRouter()
class ChatRequest(BaseModel):
    user_id: str
    message: str = Field(min_length=1, max_length=10_000)
    thread_id: str | None = None
    exam_id: str | None = None

def configure(orchestrator, bridge, redis, extractor):
    @router.post("/chat")
    async def chat(request: ChatRequest):
        memory = EpisodicMemory(redis, request.thread_id or f"main:{request.user_id}")
        profile = await bridge.state_get_profile(request.user_id)
        extracted = await extractor.extract_chat(OrchestratorInput(
            user_id=request.user_id,
            exam_id=request.exam_id,
            user_message=request.message,
            episodic_window=memory.get_window(),
            semantic_profile=profile,
        ))
        output = await orchestrator.run(extracted.orchestrator_input)
        memory.add_turn("user", request.message); memory.add_turn("assistant", output.assistant_response)
        return output
    @router.post("/doubt")
    async def doubt(request: ChatRequest):
        request.message = "doubt: " + request.message
        return await chat(request)
    return router
