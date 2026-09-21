from fastapi import APIRouter
from pydantic import BaseModel, Field
from ai_services.agents.agent1_analyzer import Agent1Analyzer
from ai_services.agents.agent2_report_generator import Agent2ReportGenerator
from ai_services.agents.agent3_report_editor import Agent3ReportEditor
from ai_services.schemas.analyzer_schemas import AnalyzerInput
from ai_services.schemas.report_schemas import EditorInput, NodeScoreLookup, ReportGeneratorInput

router = APIRouter()

class StrategyRequest(BaseModel):
    analyzer_input: AnalyzerInput
    custom_instructions: list[str] = Field(default_factory=list)
    doc_id: str = "strategy"


def configure(analyzer: Agent1Analyzer, generator: Agent2ReportGenerator, editor: Agent3ReportEditor, extractor):
    @router.post("/strategy/generate")
    async def generate(request: StrategyRequest):
        extracted = await extractor.extract_strategy(
            request.analyzer_input,
            request.custom_instructions,
            request.doc_id,
        )
        analysis = await analyzer.run(extracted.analyzer_input)
        draft = await generator.run(ReportGeneratorInput(
            analyzer_output=analysis,
            exam_timing_weeks=extracted.analyzer_input.exam_timing_weeks,
            custom_instructions=extracted.custom_instructions,
        ))
        edited = await editor.run(EditorInput(
            markdown_body=draft.markdown_body,
            analyzer_output_ref=analysis.analysis_id,
            node_scores_lookup=[NodeScoreLookup(node_id=score.node_id, roi_score=score.roi_score, weightage_pct=score.weightage_pct) for score in analysis.node_scores],
            doc_id=extracted.doc_id,
        ))
        return {"analysis": analysis, "draft": draft, "report": edited, "extraction": extracted.metadata}

    return router
