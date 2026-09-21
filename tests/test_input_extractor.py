import asyncio

from ai_services.agents.agent0_input_extractor import Agent0InputExtractor
from ai_services.schemas.analyzer_schemas import AnalyzerInput, DifficultyTag, NotesCoverageItem, PYQIndexItem, SyllabusNode
from ai_services.schemas.mock_schemas import MockGeneratorInput, MockMode
from ai_services.schemas.orchestrator_schemas import OrchestratorInput, SemanticProfile


def _analyzer_input() -> AnalyzerInput:
    return AnalyzerInput(
        exam_id="exam-1",
        exam_name="Algebra",
        exam_timing_weeks=6,
        syllabus_nodes=[SyllabusNode(node_id="MATH.1", title="Algebra")],
        pyq_index=[PYQIndexItem(
            pyq_id="PYQ.1",
            node_ids=["MATH.1"],
            year=2025,
            marks=4,
            difficulty_tag=DifficultyTag.medium,
        )],
        notes_coverage_map=[NotesCoverageItem(node_id="MATH.1", chunk_ids=["note-1"], coverage_score=0.2)],
    )


def test_extractor_preserves_evidence_and_normalizes_agent_inputs():
    async def run():
        extractor = Agent0InputExtractor()
        analyzer_input = _analyzer_input()

        request = await extractor.extract_ingestion_request("  Algebra   Exam ", 6, ["  Focus   on   algebra  "])
        assert request.exam_name == "Algebra Exam"
        assert request.custom_instructions == ["Focus on algebra"]

        ingestion = await extractor.extract_ingestion(analyzer_input, ["  Focus   on   algebra  ", "Focus on algebra"])
        assert ingestion.metadata.mode == "deterministic"
        assert ingestion.custom_instructions == ["Focus on algebra"]
        assert ingestion.analyzer_input.model_dump() == analyzer_input.model_dump()

        strategy = await extractor.extract_strategy(analyzer_input, ["  focus on algebra  "], "   ")
        assert strategy.doc_id == "strategy"
        assert strategy.custom_instructions == ["focus on algebra"]

        chat = await extractor.extract_chat(OrchestratorInput(
            user_id="user-1",
            user_message="  Explain   algebra  ",
            episodic_window=[],
            semantic_profile=SemanticProfile(user_id="user-1"),
        ))
        assert chat.orchestrator_input.user_message == "Explain algebra"

        mock = await extractor.extract_mock(MockGeneratorInput(
            mode=MockMode.exam_replica,
            target_node_ids=["MATH.1"],
            source_pyq_refs=["PYQ.1"],
            node_weights={"MATH.1": 1.0},
            question_count=2,
            time_limit_minutes=10,
        ))
        assert mock.mock_input.target_node_ids == ["MATH.1"]
        assert mock.mock_input.source_pyq_refs == ["PYQ.1"]

    asyncio.run(run())


def test_extractor_can_use_llm_for_instruction_normalization(monkeypatch):
    async def fake_complete_json(*_args, **_kwargs):
        return {"instructions": ["Prioritize algebra proofs"]}

    monkeypatch.setattr("ai_services.agents.agent0_input_extractor.complete_json", fake_complete_json)

    extracted = asyncio.run(
        Agent0InputExtractor("test-model").extract_ingestion(
            _analyzer_input(),
            ["Please prioritize algebra proofs and practice."],
        )
    )

    assert extracted.metadata.mode == "llm_assisted"
    assert extracted.custom_instructions == ["Prioritize algebra proofs"]