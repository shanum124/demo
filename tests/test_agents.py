import asyncio
from datetime import datetime, timezone
import pytest

from ai_services.agents.agent1_analyzer import Agent1Analyzer
from ai_services.agents.agent2_report_generator import Agent2ReportGenerator
from ai_services.agents.agent3_report_editor import Agent3ReportEditor
from ai_services.agents.agent4_mock_generator import Agent4MockGenerator
from ai_services.agents.agent5_orchestrator import Agent5Orchestrator
from ai_services.main import bridge
from ai_services.schemas.analyzer_schemas import (
    AnalyzerInput,
    NotesCoverageItem,
    PYQIndexItem,
    SyllabusNode,
    DifficultyTag,
)
from ai_services.schemas.mcp_schemas import TelemetryEvent, VectorSearchRequest
from ai_services.schemas.orchestrator_schemas import OrchestratorInput, SemanticProfile
from ai_services.schemas.report_schemas import EditorInput, NodeScoreLookup, ReportGeneratorInput
from ai_services.schemas.mock_schemas import MockGeneratorInput, MockMode


def test_all_agents_and_mcp_bridge_fallback_paths():
    async def run():
        analyzer_input = AnalyzerInput(
            exam_name="Demo",
            exam_timing_weeks=8,
            syllabus_nodes=[SyllabusNode(node_id="MATH.1", title="Algebra")],
            pyq_index=[PYQIndexItem(pyq_id="P1", node_ids=["MATH.1"], year=2025, marks=4, difficulty_tag=DifficultyTag.medium)],
            notes_coverage_map=[NotesCoverageItem(node_id="MATH.1", chunk_ids=["C1"], coverage_score=0.2)],
        )
        analyzer = await Agent1Analyzer(None, bridge).run(analyzer_input)
        assert analyzer.node_scores[0].node_id == "MATH.1"

        draft = await Agent2ReportGenerator(None, bridge).run(ReportGeneratorInput(analyzer_output=analyzer, exam_timing_weeks=8))
        edited = await Agent3ReportEditor(None, bridge).run(EditorInput(
            markdown_body=draft.markdown_body,
            analyzer_output_ref=analyzer.analysis_id,
            node_scores_lookup=[NodeScoreLookup(node_id="MATH.1", roi_score=analyzer.node_scores[0].roi_score, weightage_pct=analyzer.node_scores[0].weightage_pct)],
        ))
        assert edited.validated_markdown

        with pytest.raises(Exception, match="no LLM model"):
            await Agent4MockGenerator(None, bridge).run(MockGeneratorInput(mode=MockMode.exam_replica, target_node_ids=["MATH.1"], source_pyq_refs=["P1"], node_weights={"MATH.1": analyzer.node_scores[0].roi_score}, question_count=2, time_limit_minutes=10))

        orchestrated = await Agent5Orchestrator(None, bridge, None, Agent4MockGenerator(None, bridge)).run(OrchestratorInput(
            user_id="agent-test",
            user_message="Explain algebra",
            episodic_window=[],
            semantic_profile=SemanticProfile(user_id="agent-test"),
        ))
        assert orchestrated.assistant_response

        await bridge.vector.ingest([{"chunk_id": "C1", "node_id": "MATH.1", "text": "Algebra notes"}])
        retrieved = await bridge.vector_db_search(VectorSearchRequest(query="algebra"))
        assert any(result.chunk_id == "C1" for result in retrieved)
        result = await bridge.telemetry_log_event(TelemetryEvent(event_type="micro_challenge_result", payload={"node_id": "MATH.1", "correct": False}, ts=datetime.now(timezone.utc), user_id="agent-test"))
        assert result.logged and result.profile_updated

    asyncio.run(run())