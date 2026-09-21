from fastapi import FastAPI
from ai_services.config import get_settings
from ai_services.memory.redis_memory import InMemoryRedis
from ai_services.stores.database import build_stores
from ai_services.agents.agent6_mcp_bridge import Agent6MCPBridge
from ai_services.agents.agent4_mock_generator import Agent4MockGenerator
from ai_services.agents.agent5_orchestrator import Agent5Orchestrator
from ai_services.agents.agent0_input_extractor import Agent0InputExtractor
from ai_services.agents.agent1_analyzer import Agent1Analyzer
from ai_services.agents.agent2_report_generator import Agent2ReportGenerator
from ai_services.agents.agent3_report_editor import Agent3ReportEditor
from ai_services.routers import chat, mock, report, profile, ingestion, strategy

settings = get_settings()
vector, pyqs, syllabus, mocks, markdown = build_stores()
redis = InMemoryRedis()
bridge = Agent6MCPBridge(vector, pyqs, syllabus, mocks, markdown, redis)
extractor = Agent0InputExtractor(settings.ollama_model if settings.extractor_use_llm else None)
analyzer = Agent1Analyzer(settings.ollama_model, bridge)
report_generator = Agent2ReportGenerator(settings.ollama_model, bridge)
report_editor = Agent3ReportEditor(settings.ollama_model, bridge)
mock_generator = Agent4MockGenerator(settings.ollama_model, bridge)
orchestrator = Agent5Orchestrator(settings.ollama_model, bridge, None, mock_generator)
app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(ingestion.configure(bridge, extractor))
app.include_router(chat.configure(orchestrator, bridge, redis, extractor))
app.include_router(strategy.configure(analyzer, report_generator, report_editor, extractor))
app.include_router(mock.configure(mock_generator, bridge, extractor))
app.include_router(report.configure(markdown))
app.include_router(profile.configure(bridge))

@app.get("/health")
async def health(): return {"status": "ok", "environment": settings.environment}
