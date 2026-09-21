import json
from ai_services.schemas.mcp_schemas import *
from ai_services.schemas.orchestrator_schemas import SemanticProfile
from ai_services.schemas.mock_schemas import MockTest
from ai_services.memory.semantic_memory import SemanticMemory

class Agent6MCPBridge:
    def __init__(self, vector_store, pyq_store, syllabus_store, mock_store, markdown_store, redis_client):
        self.vector, self.pyqs, self.syllabus, self.mocks, self.markdown, self.redis = vector_store, pyq_store, syllabus_store, mock_store, markdown_store, redis_client
        self.semantic = SemanticMemory(redis_client)
    async def vector_db_search(self, request: VectorSearchRequest): return await self.vector.search(request.query, request.node_id_filter, min(request.top_k, 5), request.exam_id)
    async def markdown_store_write(self, request: MarkdownWriteRequest): return MarkdownWriteResult(success=True, version=self.markdown.write_patch(request.doc_id, request.section, request.patch))
    async def telemetry_log_event(self, event: TelemetryEvent):
        self.redis.rpush(f"telemetry:{event.user_id}", event.model_dump_json())
        await self.semantic.reducer(event.user_id)
        return TelemetryResult(logged=True, profile_updated=True)
    async def state_get_profile(self, user_id): return await self.semantic.get_profile(user_id)
    async def pyq_fetch(self, request): return self.pyqs.fetch(request.pyq_ids, request.fields)
    async def node_graph_query(self, request): return self.syllabus.graph(request.node_id, request.depth)
    async def mock_store_write(self, test_id, mock_object: MockTest): return self.mocks.write(mock_object)
