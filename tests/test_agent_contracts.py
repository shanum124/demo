import asyncio
import json

import pytest

from ai_services.agents.agent1_analyzer import Agent1Analyzer
from ai_services.agents.agent2_report_generator import Agent2ReportGenerator
from ai_services.agents.agent3_report_editor import Agent3ReportEditor
from ai_services.agents.agent4_mock_generator import Agent4MockGenerator, MockGenerationError
from ai_services.schemas.analyzer_schemas import (
    AnalyzerInput,
    AnalyzerOutput,
    DifficultyTag,
    NodeScore,
    NotesCoverageItem,
    PYQIndexItem,
    SyllabusNode,
)
from ai_services.schemas.mock_schemas import MockGeneratorInput, MockMode
from ai_services.schemas.report_schemas import EditorInput, NodeScoreLookup, ReportGeneratorInput


def _analysis() -> AnalyzerOutput:
    return AnalyzerOutput(
        analysis_id="analysis-1",
        generated_at="2026-09-20T00:00:00Z",
        node_scores=[
            NodeScore(
                node_id="MATH.1",
                weightage_pct=100.0,
                questions_asked=2,
                papers_appeared=2,
                years_appeared=[2024, 2025],
                frequency_last_5yr=1.0,
                avg_marks=4.0,
                difficulty_index=0.66,
                notes_coverage_score=0.2,
                roi_score=2.5,
                gap_flag=True,
                source_pyq_ids=["PYQ-1", "PYQ-2"],
            )
        ],
        top_roi_nodes=["MATH.1"],
        critical_gaps=["MATH.1"],
        reasoning_trace="test",
        analysis_status="success",
        failure_reason=None,
    )


def _valid_report() -> dict:
    return {
        "report_draft_id": "model-id",
        "markdown_body": (
            "## 1. Foundation and Concept Building\nMATH.1\n\n"
            "## 2. Practice and Application\nMATH.1\n\n"
            "## 3. Revision and Exam Readiness\nMATH.1"
        ),
        "phase_count": 3,
        "referenced_node_ids": ["MATH.1"],
        "generation_status": "success",
        "failure_reason": None,
    }


def test_agent2_accepts_complete_reportdraft_contract(monkeypatch):
    async def valid_complete_json(*_args, **_kwargs):
        return _valid_report()

    monkeypatch.setattr("ai_services.agents.agent2_report_generator.complete_json", valid_complete_json)
    draft = asyncio.run(
        Agent2ReportGenerator("test-model").run(
            ReportGeneratorInput(analyzer_output=_analysis(), exam_timing_weeks=6)
        )
    )

    assert draft.generation_status == "success"
    assert draft.failure_reason is None
    assert draft.report_draft_id != "model-id"
    assert draft.referenced_node_ids == ["MATH.1"]


def test_agent2_exposes_schema_validation_fallback(monkeypatch):
    async def invalid_complete_json(*_args, **_kwargs):
        return {"markdown": "wrong shape"}

    monkeypatch.setattr("ai_services.agents.agent2_report_generator.complete_json", invalid_complete_json)
    draft = asyncio.run(
        Agent2ReportGenerator("test-model").run(
            ReportGeneratorInput(analyzer_output=_analysis(), exam_timing_weeks=6)
        )
    )

    assert draft.generation_status == "deterministic_fallback"
    assert draft.failure_reason == "report_schema_validation_failed"
    assert draft.phase_count == 3


class _MarkdownBridge:
    def __init__(self):
        self.writes = []

    async def markdown_store_write(self, request):
        self.writes.append(request)


def _editor_input() -> EditorInput:
    return EditorInput(
        markdown_body=_valid_report()["markdown_body"],
        analyzer_output_ref="analysis-1",
        node_scores_lookup=[NodeScoreLookup(node_id="MATH.1", roi_score=2.5, weightage_pct=100.0)],
    )


def _valid_editor_output(markdown: str | None = None) -> dict:
    return {
        "validated_markdown": markdown or _valid_report()["markdown_body"],
        "validation_report": {
            "claims_checked": 5,
            "claims_removed": 0,
            "formatting_fixes": 0,
            "hallucination_flags": [],
        },
        "status": "approved",
        "generation_status": "success",
        "failure_reason": None,
    }


def test_agent3_accepts_complete_editoroutput_contract(monkeypatch):
    async def valid_complete_json(*_args, **_kwargs):
        return _valid_editor_output()

    bridge = _MarkdownBridge()
    monkeypatch.setattr("ai_services.agents.agent3_report_editor.complete_json", valid_complete_json)
    output = asyncio.run(Agent3ReportEditor("test-model", bridge).run(_editor_input()))

    assert output.generation_status == "success"
    assert output.status == "approved"
    assert len(bridge.writes) == 1


def test_agent3_exposes_schema_fallback_and_rejects_unknown_node(monkeypatch):
    async def invalid_complete_json(*_args, **_kwargs):
        return {"markdown": "wrong shape"}

    bridge = _MarkdownBridge()
    monkeypatch.setattr("ai_services.agents.agent3_report_editor.complete_json", invalid_complete_json)
    output = asyncio.run(Agent3ReportEditor("test-model", bridge).run(_editor_input()))

    assert output.generation_status == "deterministic_fallback"
    assert output.failure_reason == "editor_schema_validation_failed"

    async def unknown_node_complete_json(*_args, **_kwargs):
        return _valid_editor_output(
            _valid_report()["markdown_body"].replace("MATH.1", "MATH.404")
        )

    monkeypatch.setattr("ai_services.agents.agent3_report_editor.complete_json", unknown_node_complete_json)
    rejected = asyncio.run(Agent3ReportEditor("test-model", _MarkdownBridge()).run(_editor_input()))
    assert rejected.generation_status == "deterministic_fallback"
    assert rejected.failure_reason == "editor_semantic_validation_failed"


class _MockBridge:
    def __init__(self):
        self.writes = []

    async def pyq_fetch(self, request):
        return [{"pyq_id": pyq_id, "node_ids": ["MATH.1"], "year": 2025, "marks": 4, "difficulty_tag": "medium", "dna_tags": []} for pyq_id in request.pyq_ids]

    async def mock_store_write(self, test_id, test):
        self.writes.append((test_id, test))


def _mock_input() -> MockGeneratorInput:
    return MockGeneratorInput(
        mode=MockMode.exam_replica,
        target_node_ids=["MATH.1"],
        source_pyq_refs=["P1"],
        node_weights={"MATH.1": 2.5},
        question_count=2,
        time_limit_minutes=10,
    )


def _mock_result_from_request(request_json: str) -> dict:
    request = json.loads(request_json)
    test_id = request["validation_metadata"]["test_id"]
    question_ids = request["validation_metadata"]["question_ids"]
    questions = [
        {
            "question_id": question_id,
            "node_id": "MATH.1",
            "source_pyq_dna": "P1",
            "question_text": f"Question {index + 1}?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_option_index": 0,
            "marks": 1.0,
            "negative_marks": 0.25,
            "difficulty_tag": "medium",
            "explanation": "Evidence-grounded explanation.",
        }
        for index, question_id in enumerate(question_ids)
    ]
    return {
        "test_id": test_id,
        "mode": "exam_replica",
        "questions": questions,
        "total_marks": float(len(questions)),
        "time_limit_minutes": 10,
    }


def test_agent4_accepts_complete_mocktest_contract(monkeypatch):
    async def valid_complete_json(_model, _prompt, request_json, _schema):
        return _mock_result_from_request(request_json)

    bridge = _MockBridge()
    monkeypatch.setattr("ai_services.agents.agent4_mock_generator.complete_json", valid_complete_json)
    output = asyncio.run(Agent4MockGenerator("test-model", bridge).run(_mock_input()))

    assert len(output.questions) == 2
    assert {question.source_pyq_dna for question in output.questions} == {"P1"}
    assert len(bridge.writes) == 1


def test_agent4_rejects_missing_application_id_and_pyq_reference(monkeypatch):
    async def invalid_complete_json(_model, _prompt, request_json, _schema):
        result = _mock_result_from_request(request_json)
        result["test_id"] = "model-owned-id"
        result["questions"][0]["source_pyq_dna"] = "UNKNOWN_PYQ"
        return result

    monkeypatch.setattr("ai_services.agents.agent4_mock_generator.complete_json", invalid_complete_json)
    with pytest.raises(MockGenerationError, match="unexpected test ID") as exc_info:
        asyncio.run(Agent4MockGenerator("test-model", _MockBridge()).run(_mock_input()))
    assert exc_info.value.reason == "mock_metadata_validation_failed"


def test_agent1_to_agent4_contract_chain(monkeypatch):
    async def report_complete_json(*_args, **_kwargs):
        return _valid_report()

    async def editor_complete_json(*_args, **_kwargs):
        return _valid_editor_output()

    async def mock_complete_json(_model, _prompt, request_json, _schema):
        return _mock_result_from_request(request_json)

    monkeypatch.setattr("ai_services.agents.agent2_report_generator.complete_json", report_complete_json)
    monkeypatch.setattr("ai_services.agents.agent3_report_editor.complete_json", editor_complete_json)
    monkeypatch.setattr("ai_services.agents.agent4_mock_generator.complete_json", mock_complete_json)

    async def run_chain():
        analysis = await Agent1Analyzer().run(AnalyzerInput(
            exam_name="Algebra",
            exam_timing_weeks=6,
            syllabus_nodes=[SyllabusNode(node_id="MATH.1", title="Algebra")],
            pyq_index=[PYQIndexItem(
                pyq_id="P1",
                node_ids=["MATH.1"],
                year=2025,
                marks=4,
                difficulty_tag=DifficultyTag.medium,
            )],
            notes_coverage_map=[NotesCoverageItem(node_id="MATH.1", chunk_ids=["C1"], coverage_score=0.2)],
        ))
        draft = await Agent2ReportGenerator("test-model").run(
            ReportGeneratorInput(analyzer_output=analysis, exam_timing_weeks=6)
        )
        editor_bridge = _MarkdownBridge()
        edited = await Agent3ReportEditor("test-model", editor_bridge).run(EditorInput(
            markdown_body=draft.markdown_body,
            analyzer_output_ref=analysis.analysis_id,
            node_scores_lookup=[NodeScoreLookup(
                node_id=score.node_id,
                roi_score=score.roi_score,
                weightage_pct=score.weightage_pct,
            ) for score in analysis.node_scores],
        ))
        mock_bridge = _MockBridge()
        mock = await Agent4MockGenerator("test-model", mock_bridge).run(MockGeneratorInput(
            mode=MockMode.exam_replica,
            target_node_ids=analysis.top_roi_nodes,
            source_pyq_refs=["P1"],
            node_weights={score.node_id: score.roi_score for score in analysis.node_scores},
            question_count=2,
            time_limit_minutes=10,
        ))
        return analysis, draft, edited, mock

    analysis, draft, edited, mock = asyncio.run(run_chain())
    assert analysis.analysis_status == "success"
    assert draft.generation_status == "success"
    assert edited.generation_status == "success"
    assert len(mock.questions) == 2
