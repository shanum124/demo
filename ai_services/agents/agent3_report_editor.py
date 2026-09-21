import logging
import re
from ai_services.schemas.report_schemas import *
from ai_services.schemas.mcp_schemas import MarkdownWriteRequest
from .llm import complete_json
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class ReportRejectedError(RuntimeError): pass


class Agent3ReportEditor:
    SYSTEM_PROMPT = """You are the STRATEGY EDITOR AGENT of an Adaptive Learning Engine.

You may improve wording and organization only. Do not introduce node IDs, scores,
facts, or phases absent from the supplied report and node-score lookup. Keep the
three required phase headings exactly as written:

1. Foundation and Concept Building
2. Practice and Application
3. Revision and Exam Readiness

Return ONE JSON object with EXACTLY these required fields:

{
    "validated_markdown": "the complete edited strategy Markdown",
    "validation_report": {
        "claims_checked": 0,
        "claims_removed": 0,
        "formatting_fixes": 0,
        "hallucination_flags": []
    },
    "status": "approved",
    "generation_status": "success",
    "failure_reason": null
}

`status` must be one of `approved`, `revised`, or `rejected`.
`generation_status` must be `success` and `failure_reason` must be null. The
application owns fallback status and failure reasons. All fields are required.
Return JSON only, with no wrapping object and no Markdown fences."""

    def __init__(self, model=None, mcp_bridge=None):
        self.model = model
        self.bridge = mcp_bridge

    @staticmethod
    def _validate_markdown(markdown_body: str, known_node_ids: set[str], expected_phase_count: int) -> tuple[str, ValidationReport, str]:
        required_headings = (
            "## 1. Foundation and Concept Building",
            "## 2. Practice and Application",
            "## 3. Revision and Exam Readiness",
        )
        node_pattern = re.compile(r"\b[A-Z][A-Z0-9_]*(?:\.[A-Z0-9_]+)+\b")
        lines = markdown_body.splitlines()
        cleaned_lines: list[str] = []
        invalid_references: set[str] = set()
        removed = 0

        for line in lines:
            references = set(node_pattern.findall(line))
            unknown = references - known_node_ids
            if unknown:
                invalid_references.update(unknown)
                removed += 1
                continue
            cleaned_lines.append(line)

        cleaned = "\n".join(cleaned_lines).strip()
        present_phases = sum(heading in cleaned for heading in required_headings)
        flags = [f"invalid_node_reference:{node_id}" for node_id in sorted(invalid_references)]
        if present_phases != expected_phase_count:
            flags.append("invalid_phase_structure")
        status = "rejected" if flags else "approved"
        report = ValidationReport(
            claims_checked=len(lines),
            claims_removed=removed,
            formatting_fixes=0,
            hallucination_flags=flags,
        )
        return cleaned, report, status

    async def _persist(self, input_data: EditorInput, output: EditorOutput) -> EditorOutput:
        if self.bridge is not None:
            await self.bridge.markdown_store_write(
                MarkdownWriteRequest(doc_id=input_data.doc_id, section="strategy", patch=output.validated_markdown)
            )
        return output

    async def run(self, input_data: EditorInput) -> EditorOutput:
        known = {x.node_id for x in input_data.node_scores_lookup}
        fallback_markdown, fallback_validation, fallback_status = self._validate_markdown(
            input_data.markdown_body, known, input_data.expected_phase_count
        )
        fallback_reason = "editor_model_unavailable" if self.model is None else "editor_schema_validation_failed"
        fallback = EditorOutput(
            validated_markdown=fallback_markdown,
            validation_report=fallback_validation,
            status=fallback_status,
            generation_status="deterministic_fallback",
            failure_reason=fallback_reason,
        )
        if self.model is None:
            return await self._persist(input_data, fallback)

        try:
            result = await complete_json(self.model, self.SYSTEM_PROMPT, input_data.model_dump_json(), EditorOutput)
            candidate = EditorOutput.model_validate(result)
            markdown, validation_report, status = self._validate_markdown(
                candidate.validated_markdown, known, input_data.expected_phase_count
            )
            if status == "rejected":
                semantic_fallback = fallback.model_copy(update={"failure_reason": "editor_semantic_validation_failed"})
                return await self._persist(input_data, semantic_fallback)
            output = candidate.model_copy(update={
                "validated_markdown": markdown,
                "validation_report": validation_report,
                "status": status,
                "generation_status": "success",
                "failure_reason": None,
            })
            return await self._persist(input_data, output)
        except ValidationError:
            logger.exception("Report editor schema validation failed", extra={"doc_id": input_data.doc_id})
            return await self._persist(input_data, fallback)
        except Exception:
            logger.exception("Report editing failed; preserving deterministic report", extra={"doc_id": input_data.doc_id})
            fallback = fallback.model_copy(update={"failure_reason": "editor_generation_failed"})
            return await self._persist(input_data, fallback)
