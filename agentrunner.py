import asyncio

from ai_services.agents.agent1_analyzer import Agent1Analyzer
from ai_services.schemas.analyzer_schemas import (
    AnalyzerInput,
    SyllabusNode,
    PYQIndexItem,
    NotesCoverageItem,
    DifficultyTag,
)


async def main():

    # -------------------------
    # 1. Syllabus
    # -------------------------
    syllabus = [
        SyllabusNode(
            node_id="unit1_topic1",
            title="Decision Tree Learning",
            parent_id=None
        )
    ]

    # -------------------------
    # 2. PYQ data
    # -------------------------
    pyqs = [
        PYQIndexItem(
            pyq_id="pyq_2024_01",
            node_ids=["unit1_topic1"],
            year=2024,
            marks=10,
            difficulty_tag=DifficultyTag.medium
        )
    ]

    # -------------------------
    # 3. Notes coverage
    # -------------------------
    coverage = [
        NotesCoverageItem(
            node_id="unit1_topic1",
            chunk_ids=["chunk_001"],
            coverage_score=0.3
        )
    ]

    # -------------------------
    # 4. Create AnalyzerInput
    # -------------------------
    input_data = AnalyzerInput(
        exam_name="Test Exam",
        exam_timing_weeks=10,
        syllabus_nodes=syllabus,
        pyq_index=pyqs,
        notes_coverage_map=coverage
    )

    # -------------------------
    # 5. Create Analyzer
    # -------------------------
    analyzer = Agent1Analyzer(
        anthropic_client="gemma4:31b-cloud",
        mcp_bridge=None
    )

    # -------------------------
    # 6. Run Analyzer
    # -------------------------
    result = await analyzer.run(input_data)

    # -------------------------
    # 7. Print result
    # -------------------------
    print("\n========== ANALYZER OUTPUT ==========\n")

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())