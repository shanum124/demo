import asyncio

from ai_services.agents.agent1_analyzer import Agent1Analyzer
from ai_services.agents.agent2_report_generator import Agent2ReportGenerator
from ai_services.schemas.analyzer_schemas import AnalyzerInput
from ai_services.schemas.report_schemas import ReportGeneratorInput
from ai_services.routers.ingestion import (
    calculate_notes_coverage,
    parse_pyq_documents,
    parse_syllabus_structure,
)
from fastapi.testclient import TestClient
from ai_services.main import app


def test_parse_syllabus_structure_preserves_real_hierarchy():
    sample = """
    UNIT 1: INTRODUCTION
    Topic: Variables and Expressions
    Topic: Control Flow

    UNIT 2: DATA STRUCTURES
    Topic: Arrays
    """
    nodes = parse_syllabus_structure(sample)

    assert nodes
    assert not any(node.node_id.startswith("GENERAL.") for node in nodes)
    assert any("UNIT.1" in node.node_id for node in nodes)
    assert any(node.title.lower().startswith("variables") or node.title.lower().startswith("control") for node in nodes)


def test_notes_coverage_is_based_on_real_evidence():
    nodes = [
        {"node_id": "UNIT.1", "title": "Variables and Expressions"},
        {"node_id": "UNIT.2", "title": "Arrays"},
    ]
    note_chunks = [
        {"chunk_id": "c1", "node_id": "UNIT.1", "text": "variables and expressions are core concepts in programming"},
        {"chunk_id": "c2", "node_id": "UNIT.2", "text": "arrays store a sequence of values"},
    ]

    coverage = calculate_notes_coverage(nodes, note_chunks)
    assert coverage["UNIT.1"] > 0
    assert coverage["UNIT.2"] > 0


def test_pyq_parser_retains_source_metadata_and_real_node_mapping():
    nodes = parse_syllabus_structure("UNIT 1: Algebra\nTopic: Quadratic Equations")
    pyqs = parse_pyq_documents(
        [("algebra_2024.txt", "2024 Paper\nQ1. Solve a quadratic equation. [4 marks]")],
        nodes,
    )

    assert len(pyqs) == 1
    assert pyqs[0].year == 2024
    assert pyqs[0].marks == 4
    assert pyqs[0].source_document == "algebra_2024.txt"
    assert pyqs[0].node_ids == ["UNIT.1.TOPIC.1"]


def test_pyq_parser_accepts_colon_delimited_question_labels():
    nodes = parse_syllabus_structure("UNIT 1: Operating Systems\nTopic: Process Scheduling")
    pyqs = parse_pyq_documents(
        [("os_2025.txt", "2025 Paper\nQuestion 1: Process Scheduling [10 marks]")],
        nodes,
    )

    assert len(pyqs) == 1
    assert pyqs[0].question_number == "1"
    assert pyqs[0].marks == 10
    assert pyqs[0].node_ids == ["UNIT.1.TOPIC.1"]


def test_ingest_endpoint_returns_evidence_backed_analyzer_input():
    client = TestClient(app)
    response = client.post(
        "/ingest",
        data={"exam_name": "Algebra", "exam_timing_weeks": "6"},
        files=[
            ("syllabus", ("syllabus.txt", "UNIT 1: Algebra\nTopic: Quadratic Equations", "text/plain")),
            ("pyqs", ("paper_2024.txt", "2024 Paper\nQ1. Solve a quadratic equation. [4 marks]", "text/plain")),
            ("notes", ("notes.txt", "Quadratic equations have roots, coefficients, and a discriminant.", "text/plain")),
        ],
    )

    assert response.status_code == 200
    result = response.json()
    analyzer_input = result["analyzer_input"]
    assert result["status"] == "COMPLETED"
    assert result["document_counts"]["note_chunks"] == 1
    assert analyzer_input["syllabus_nodes"][1]["node_id"] == "UNIT.1.TOPIC.1"
    assert analyzer_input["pyq_index"][0]["node_ids"] == ["UNIT.1.TOPIC.1"]
    assert analyzer_input["notes_coverage_map"][1]["coverage_score"] > 0

    async def verify_strategy():
        analysis = await Agent1Analyzer(None, None).run(AnalyzerInput.model_validate(analyzer_input))
        topic_score = next(score for score in analysis.node_scores if score.node_id == "UNIT.1.TOPIC.1")
        draft = await Agent2ReportGenerator(None, None).run(
            ReportGeneratorInput(analyzer_output=analysis, exam_timing_weeks=6)
        )
        return analysis, topic_score, draft

    analysis, topic_score, draft = asyncio.run(verify_strategy())
    assert analysis.analysis_status == "success"
    assert topic_score.questions_asked == 1
    assert topic_score.years_appeared == [2024]
    assert topic_score.roi_score > 0
    assert draft.phase_count == 3
    assert "Foundation and Concept Building" in draft.markdown_body
    assert "Practice and Application" in draft.markdown_body
    assert "Revision and Exam Readiness" in draft.markdown_body


def test_strategy_endpoint_returns_renderable_markdown_without_an_llm(monkeypatch):
    monkeypatch.setattr("ai_services.main.report_generator.model", None)
    monkeypatch.setattr("ai_services.main.report_editor.model", None)
    client = TestClient(app)
    analyzer_input = {
        "exam_id": "strategy-contract-check",
        "exam_name": "Algebra",
        "exam_timing_weeks": 6,
        "syllabus_nodes": [
            {"node_id": "UNIT.1", "title": "Algebra", "node_type": "unit"},
            {"node_id": "UNIT.1.TOPIC.1", "title": "Quadratic Equations", "parent_id": "UNIT.1"},
        ],
        "pyq_index": [
            {
                "pyq_id": "pyq-1",
                "node_ids": ["UNIT.1.TOPIC.1"],
                "year": 2025,
                "marks": 4,
                "difficulty_tag": "medium",
            }
        ],
        "notes_coverage_map": [
            {"node_id": "UNIT.1", "chunk_ids": [], "coverage_score": 0.0},
            {"node_id": "UNIT.1.TOPIC.1", "chunk_ids": ["note-1"], "coverage_score": 0.3},
        ],
    }

    response = client.post("/strategy/generate", json={"analyzer_input": analyzer_input})

    assert response.status_code == 200
    result = response.json()
    assert result["draft"]["generation_status"] == "deterministic_fallback"
    assert result["report"]["validated_markdown"]
    assert "Foundation and Concept Building" in result["report"]["validated_markdown"]
    assert "Practice and Application" in result["report"]["validated_markdown"]
    assert "Revision and Exam Readiness" in result["report"]["validated_markdown"]
