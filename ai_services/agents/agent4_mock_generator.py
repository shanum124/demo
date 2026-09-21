import json
import logging
from uuid import uuid4
from pydantic import ValidationError
from ai_services.schemas.mcp_schemas import PYQFetchRequest
from ai_services.schemas.mock_schemas import *
from .llm import complete_json

logger = logging.getLogger(__name__)


class MockGenerationError(RuntimeError):
    """Raised when a validated evidence-grounded mock cannot be generated."""

    def __init__(self, reason: str, message: str, status_code: int):
        super().__init__(message)
        self.reason = reason
        self.status_code = status_code


class Agent4MockGenerator:
    SYSTEM_PROMPT = """You are the MOCK GENERATOR AGENT of an AI-powered personalized learning system.
Generate a short, targeted, adaptive MCQ mock based ONLY on the student's CURRENT_TOPICS,
trusted Analyzer report, USER_REPORT, and PYQ metadata supplied by the application.
Reinforce weak areas and test important/frequently asked concepts. Never introduce topics
outside CURRENT_TOPICS and never invent weak topics. Prefer weak topics first, then VERY_HIGH
and HIGH importance concepts, repeated concepts, and repeated PYQ patterns.
Use PYQ metadata as DNA only; do not copy source wording or expose raw documents.
Every question needs question text, exactly four options, exactly one correct answer,
explanation, topic/node ID, difficulty, tested concept/source DNA, marks, and negative marks.
Use the application-requested count; otherwise produce 10-15 questions.
Return ONE JSON object with EXACTLY these required top-level fields:

{
    "test_id": "the application-provided test ID",
    "mode": "exam_replica or diagnostic_drill from request",
    "questions": [
        {
            "question_id": "the application-provided question ID",
            "node_id": "one requested target node ID",
            "source_pyq_dna": "pipe-separated supplied PYQ IDs, or no_pyq_evidence only when none were supplied",
            "question_text": "non-empty question",
            "options": ["option 1", "option 2", "option 3", "option 4"],
            "correct_option_index": 0,
            "marks": 1.0,
            "negative_marks": 0.25,
            "difficulty_tag": "easy, medium, or hard",
            "explanation": "non-empty explanation"
        }
    ],
    "total_marks": 1.0,
    "time_limit_minutes": 10
}

Use exactly the supplied test ID, question IDs, mode, requested count, time limit, target
node IDs, and source PYQ IDs. `total_marks` must equal the sum of all question marks.
All fields are required. Return JSON only with no wrapper and no Markdown fences."""


    def __init__(self, model=None, mcp_bridge=None):
        self.model = model
        self.bridge = mcp_bridge

    def _compute_question_distribution(self, input_data: MockGeneratorInput) -> dict[str, int]:
        weights = input_data.node_weights if input_data.mode == MockMode.exam_replica else input_data.weakness_scores
        total = sum(weights.values()) or 1
        raw = {node_id: input_data.question_count * weights[node_id] / total for node_id in input_data.target_node_ids}
        result = {node_id: int(weight) for node_id, weight in raw.items()}
        for node_id in sorted(input_data.target_node_ids, key=lambda item: raw[item] - result[item], reverse=True)[:input_data.question_count - sum(result.values())]:
            result[node_id] += 1
        return result

    @staticmethod
    def _validate_semantics(test: MockTest, input_data: MockGeneratorInput, allowed_pyq_ids: set[str], expected_test_id: str, expected_question_ids: set[str]) -> None:
        if test.test_id != expected_test_id:
            raise MockGenerationError("mock_metadata_validation_failed", "The model returned an unexpected test ID.", 422)
        if {question.question_id for question in test.questions} != expected_question_ids:
            raise MockGenerationError("mock_metadata_validation_failed", "The model did not return the application-provided question IDs exactly once.", 422)
        if len(test.questions) != input_data.question_count:
            raise MockGenerationError("mock_semantic_validation_failed", "The model did not return the requested number of questions.", 422)
        if test.mode != input_data.mode or test.time_limit_minutes != input_data.time_limit_minutes:
            raise MockGenerationError("mock_metadata_validation_failed", "The model returned a mock with mismatched mode or time limit.", 422)
        if test.total_marks != sum(question.marks for question in test.questions):
            raise MockGenerationError("mock_semantic_validation_failed", "The model total_marks does not equal the sum of question marks.", 422)
        for question in test.questions:
            if question.node_id not in input_data.target_node_ids:
                raise MockGenerationError("mock_semantic_validation_failed", "The model returned a question outside analyzer-approved target nodes.", 422)
            if not all(option.strip() for option in question.options) or len(set(question.options)) != 4:
                raise MockGenerationError("mock_semantic_validation_failed", "Every question must contain four distinct non-empty options.", 422)
            if not question.explanation.strip():
                raise MockGenerationError("mock_semantic_validation_failed", "Every question must include a non-empty explanation.", 422)
            if allowed_pyq_ids:
                dna_ids = {item.strip() for item in question.source_pyq_dna.split("|") if item.strip()}
                if not dna_ids or not dna_ids.issubset(allowed_pyq_ids):
                    raise MockGenerationError("mock_source_pyq_validation_failed", "Question source_pyq_dna must reference supplied PYQ IDs only.", 422)
            elif question.source_pyq_dna != "no_pyq_evidence":
                raise MockGenerationError("mock_source_pyq_validation_failed", "Questions without PYQ evidence must declare no_pyq_evidence.", 422)

    async def run(self, input_data: MockGeneratorInput) -> MockTest:
        if self.model is None:
            raise MockGenerationError("mock_model_unavailable", "Mock generation is unavailable because no LLM model is configured.", 503)
        try:
            source_metadata = await self.bridge.pyq_fetch(PYQFetchRequest(
                pyq_ids=input_data.source_pyq_refs,
                fields=["pyq_id", "node_ids", "year", "marks", "difficulty_tag", "dna_tags"],
            ))
        except Exception as exc:
            logger.exception("Mock PYQ metadata lookup failed", extra={"target_nodes": input_data.target_node_ids, "source_pyq_count": len(input_data.source_pyq_refs)})
            raise MockGenerationError("mock_internal_processing_failed", "Unable to load PYQ metadata for mock generation.", 500) from exc
        available_pyq_ids = {record["pyq_id"] for record in source_metadata}
        missing_pyq_ids = set(input_data.source_pyq_refs) - available_pyq_ids
        if missing_pyq_ids:
            raise MockGenerationError("mock_source_pyq_validation_failed", "One or more requested PYQ references do not exist.", 422)
        logger.info(
            "Generating adaptive mock",
            extra={"target_nodes": input_data.target_node_ids, "source_pyq_refs": input_data.source_pyq_refs, "mode": input_data.mode.value},
        )
        test_id = str(uuid4())
        question_ids = [str(uuid4()) for _ in range(input_data.question_count)]
        metadata_prompt = {
            "request": input_data.model_dump(),
            "source_pyq_metadata": source_metadata,
            "validation_metadata": {"test_id": test_id, "question_ids": question_ids},
            "instruction": "Use metadata as question DNA only. Do not reproduce source wording or claim access to full text.",
        }
        node_distribution = self._compute_question_distribution(input_data)
        metadata_prompt["question_distribution"] = node_distribution
        try:
            result = await complete_json(self.model, self.SYSTEM_PROMPT, json.dumps(metadata_prompt), MockTest)
            test = MockTest.model_validate(result)
            self._validate_semantics(test, input_data, available_pyq_ids, test_id, set(question_ids))
        except MockGenerationError:
            raise
        except ValidationError as exc:
            logger.exception("Mock schema validation failed", extra={"target_nodes": input_data.target_node_ids, "source_pyq_count": len(input_data.source_pyq_refs)})
            raise MockGenerationError("mock_schema_validation_failed", "The model response did not match the required mock schema.", 422) from exc
        except Exception as exc:
            logger.exception("Mock generation failed", extra={"target_node_count": len(input_data.target_node_ids)})
            raise MockGenerationError("mock_generation_failed", "Mock generation failed before a validated test could be produced.", 502) from exc
        await self.bridge.mock_store_write(test.test_id, test)
        return test
