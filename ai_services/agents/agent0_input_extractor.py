import json

from ai_services.agents.llm import complete_json
from ai_services.schemas.analyzer_schemas import AnalyzerInput
from ai_services.schemas.extractor_schemas import (
    ExtractedChatInput,
    ExtractedIngestionInput,
    ExtractedIngestionRequest,
    ExtractedMockInput,
    ExtractedStrategyInput,
    ExtractorMetadata,
    InstructionExtraction,
)
from ai_services.schemas.mock_schemas import MockGeneratorInput
from ai_services.schemas.orchestrator_schemas import OrchestratorInput


class Agent0InputExtractor:
    """Produces validated, minimal agent inputs without changing evidence fields."""

    SYSTEM_PROMPT = """Extract concise learner instructions from the supplied text.
Return JSON only with an `instructions` string array. Keep only actionable study
preferences. Do not create topics, facts, dates, scores, IDs, or claims. Do not
rewrite the syllabus, PYQ evidence, learner message, or any structured fields."""

    def __init__(self, model=None):
        self.model = model

    @staticmethod
    def _clean_instructions(instructions: list[str]) -> list[str]:
        cleaned: list[str] = []
        for instruction in instructions:
            if not isinstance(instruction, str):
                continue
            normalized = " ".join(instruction.split()).strip()
            if normalized and normalized not in cleaned:
                cleaned.append(normalized[:500])
            if len(cleaned) == 8:
                break
        return cleaned

    async def _extract_instructions(self, instructions: list[str]) -> tuple[list[str], ExtractorMetadata]:
        cleaned = self._clean_instructions(instructions)
        if self.model is None or not cleaned:
            return cleaned, ExtractorMetadata()
        try:
            result = await complete_json(
                self.model,
                self.SYSTEM_PROMPT,
                json.dumps({"instructions": cleaned}),
                InstructionExtraction,
            )
            extracted = InstructionExtraction.model_validate(result)
            normalized = self._clean_instructions(extracted.instructions)
            return normalized or cleaned, ExtractorMetadata(mode="llm_assisted")
        except Exception:
            return cleaned, ExtractorMetadata()

    async def extract_ingestion(
        self,
        analyzer_input: AnalyzerInput,
        custom_instructions: list[str],
    ) -> ExtractedIngestionInput:
        instructions, metadata = await self._extract_instructions(custom_instructions)
        return ExtractedIngestionInput(
            analyzer_input=AnalyzerInput.model_validate(analyzer_input.model_dump()),
            custom_instructions=instructions,
            metadata=metadata,
        )

    async def extract_ingestion_request(
        self,
        exam_name: str,
        exam_timing_weeks: int,
        custom_instructions: list[str],
    ) -> ExtractedIngestionRequest:
        instructions, metadata = await self._extract_instructions(custom_instructions)
        return ExtractedIngestionRequest(
            exam_name=" ".join(exam_name.split()).strip(),
            exam_timing_weeks=exam_timing_weeks,
            custom_instructions=instructions,
            metadata=metadata,
        )

    async def extract_strategy(
        self,
        analyzer_input: AnalyzerInput,
        custom_instructions: list[str],
        doc_id: str,
    ) -> ExtractedStrategyInput:
        instructions, metadata = await self._extract_instructions(custom_instructions)
        return ExtractedStrategyInput(
            analyzer_input=AnalyzerInput.model_validate(analyzer_input.model_dump()),
            custom_instructions=instructions,
            doc_id=" ".join(doc_id.split()).strip() or "strategy",
            metadata=metadata,
        )

    async def extract_chat(self, input_data: OrchestratorInput) -> ExtractedChatInput:
        message = " ".join(input_data.user_message.split()).strip()
        if not message:
            raise ValueError("message must not be empty")
        return ExtractedChatInput(
            orchestrator_input=input_data.model_copy(update={"user_message": message}),
        )

    async def extract_mock(self, input_data: MockGeneratorInput) -> ExtractedMockInput:
        target_node_ids = list(dict.fromkeys(node_id.strip() for node_id in input_data.target_node_ids if node_id.strip()))
        source_pyq_refs = list(dict.fromkeys(pyq_id.strip() for pyq_id in input_data.source_pyq_refs if pyq_id.strip()))
        mock_input = MockGeneratorInput.model_validate({
            **input_data.model_dump(),
            "target_node_ids": target_node_ids,
            "source_pyq_refs": source_pyq_refs,
        })
        return ExtractedMockInput(mock_input=mock_input)