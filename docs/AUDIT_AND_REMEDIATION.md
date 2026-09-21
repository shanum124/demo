# Audit and Remediation

## 1. Executive summary

The repository has a real Adaptive Learning Engine architecture in place, but the production execution path is broken at the upstream data layer. The most important failure is that the backend flattens syllabus, PYQ, and notes data into generic placeholder nodes before analysis. That causes the analyzer to receive empty evidence, producing `GENERAL.001 ... GENERAL.050` nodes with zero PYQ coverage and zero notes coverage. This is not a prompt issue; it is a data-pipeline integrity issue.

The repository also mixes application orchestration and AI logic in the Node backend, uses weak embedding behavior in the Qdrant store, and has a report generator that permits non-deterministic fallback output instead of enforcing the intended three-phase plan. The system needs a clearer separation between:

- Node/Express concerns: auth, uploads, orchestration, persistence, user-facing state
- Python AI service: parsing, semantic matching, coverage analysis, analyzer metrics, report generation, RAG
- vector stores: chunk retrieval and evidence grounding

## 2. Current architecture

Before remediation, the repo had the following flow:

1. Frontend sends upload/strategy data to the Node backend.
2. The Node backend aggregates syllabus text into a generic string and produces synthetic `GENERAL.*` nodes.
3. The strategy request sends `pyq_index: []` and `notes_coverage_map` with zero coverage.
4. The Python Analyzer receives empty evidence and computes a mostly empty result.
5. The report generator uses the analyzer output and a generic markdown fallback.
6. The mock generator and orchestrator rely on weak or generic node IDs and empty metadata.
7. The vector store uses hashed vectors instead of semantic embeddings.

The remediated setup path now forwards separate syllabus, PYQ, and notes files from Node to Python. Python extracts and normalizes the documents, derives source-backed nodes and metadata, indexes notes, calculates coverage, produces `AnalyzerInput`, and then generates the strategy. The following items remain incomplete: per-exam storage namespaces, PDF page-level metadata, reranking/citation-aware RAG generation, production Celery job persistence, and an application-wide authorization/security review.

## 3. Intended architecture

The correct architecture should be:

Frontend
  -> Node/Express API
  -> Python AI service ingestion
  -> syllabus parser
  -> PYQ parser and matching
  -> notes chunking + embedding
  -> deterministic analyzer
  -> strategy report generation
  -> report validation/editing
  -> mock generation
  -> RAG and orchestration

## 4. Issue register

| ID | Severity | Component | Problem | Root cause | Impact | Proposed fix | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ALE-001 | CRITICAL | backend/server/src/utils/ai-services.js | Generic `GENERAL.*` nodes replace real syllabus nodes | Syllabus documents were flattened into text lines and assigned placeholder IDs | Analyzer receives fake evidence and produces low-value strategy | Preserve syllabus structure and node metadata upstream | FIXED |
| ALE-002 | CRITICAL | ai_services/routers/ingestion.py | `/ingest` is a stub | Upload endpoint returns a task id with no extraction pipeline | No real syllabus/PYQ/notes processing | Implement parsing, normalization, matching, and persistence | FIXED |
| ALE-003 | CRITICAL | ai_services/schemas/analyzer_schemas.py | Contracts are underspecified | Missing node types and ambiguous metrics | Consumers disagree about what a node or PYQ item is | Define node types and question/paper/year metrics | FIXED |
| ALE-004 | CRITICAL | ai_services/agents/agent1_analyzer.py | Analyzer computes on empty data; LLM fallback is not safe | Input pipeline feeds empty arrays and LLM fallback masks failure | Wrong analytics and fake coverage metrics | Deterministic Python calculation with real node evidence | FIXED |
| ALE-005 | HIGH | ai_services/agents/agent2_report_generator.py | Report generator uses variable phases and weak fallback | Fallback phase count is not fixed to three phases | Strategy plan is inconsistent with the prompt | Enforce exactly three validated phases | FIXED |
| ALE-006 | HIGH | ai_services/stores/vector_store.py | Hash-based vectors are not semantic embeddings | Uses SHA256 token hashing instead of embeddings | Retrieval is not grounded in real semantics | Use a sentence-transformer model or compatible embedding contract | FIXED |
| ALE-007 | HIGH | stores and vector indexing | Data is not fully scoped per exam/user | Global local-store keys can mix evidence across uploads | Cross-exam retrieval and persistence risk | Add scoped database and vector payload migrations | OPEN |
| ALE-008 | MEDIUM | README.md | Documentation does not match architecture | Docs were written during early prototyping | Setup and runtime expectations are misleading | Update docs to describe implemented services and data flow | FIXED |
| ALE-009 | HIGH | mock generation | Generic fallback questions were produced | Fallback normalized failed LLM output into made-up content | Incorrect domain content could be served | Strict validation and explicit failure response | FIXED |
| ALE-010 | HIGH | RAG and workers | Grounded-answer/reranking and durable jobs are incomplete | Prototype retrieval and in-memory task state remain | No production-grade asynchronous or citation flow | Implement scoped RAG and durable Celery task state | OPEN |
| ALE-011 | HIGH | Agents 2 and 3 | LLM-facing output contracts omitted required status metadata; Agent 3 had a duplicate misindented prompt | Prompt/schema drift and stale prompt declaration | Report generation could fail at import time or return untraceable fallback output | Enforce exact JSON prompts, application-owned metadata, semantic node validation, and regression tests | FIXED |
| ALE-012 | HIGH | Agent 4 and mock handoff | Mock output and adaptive evidence handoff were insufficiently constrained; setup eagerly requested assessment data | Prompt/schema drift and duplicate frontend exam selection path | Invalid mocks, opaque failures, or premature/duplicate generation requests | Require analyzer weights, validate IDs/PYQ DNA/content, expose machine-readable failures, and defer fetch to Assessment tab | FIXED |

## 5. Implementation checklist

- [x] ALE-001 — Remove synthetic `GENERAL.*` defaults from the production path
- [x] ALE-002 — Implement ingestion pipeline and task status
- [x] ALE-003 — Fix schema contracts and deterministic metric semantics
- [x] ALE-004 — Make analyzer deterministic and evidence-driven
- [x] ALE-005 — Ensure exact three-phase report generation
- [x] ALE-006 — Use semantic embeddings instead of hash fallbacks
- [ ] ALE-007 — Add scoped persistence and vector migrations
- [x] ALE-008 — Refresh README and environment documentation
- [x] ALE-009 — Remove generic mock fallbacks
- [x] ALE-011 — Enforce Agents 2 and 3 report contracts and fallback reasons
- [x] ALE-012 — Enforce Agent 4 mock contract and deferred assessment generation
- [ ] ALE-010 — Complete RAG citations and durable worker orchestration

## 6. Notes

### Coverage algorithm

Coverage is deterministic. Notes are embedded with `sentence-transformers/all-MiniLM-L6-v2`, indexed in Qdrant with an `exam_id` scope, and queried with the syllabus-node title. A retrieved chunk is relevant at cosine similarity `>= 0.35`; the node score is the number of distinct relevant chunks divided by three, capped at `1.0`. This is evidence coverage, not learner mastery.

### ALE-001 through ALE-006 and ALE-009 validation

- `python -m pytest -q` verifies source-backed syllabus parsing, PYQ metadata extraction, ingestion endpoint behavior, deterministic analysis, strategy fallback structure, strict mock failure behavior, and vector retrieval.
- Node syntax validation verifies the Express controller and AI-service handoff modules parse successfully.

### Status

The critical placeholder-node/empty-evidence production path is fixed and tested. Open issues are explicitly listed above and are not represented as completed.

## ALE-011 — Repair report/editor runtime contracts

### Severity
HIGH

### Location
`ai_services/agents/agent2_report_generator.py`, `ai_services/agents/agent3_report_editor.py`, `ai_services/schemas/report_schemas.py`

### Problem
Agents 2 and 3 required status and failure metadata that their model prompts did not require. Agent 3 additionally contained a stale, duplicate `SYSTEM_PROMPT` declaration with invalid indentation.

### Solution
Both prompts now require the exact Pydantic outputs. Python assigns application-owned report IDs and fallback states. Agent 3 rejects edited reports that contain unknown node IDs or invalid phase structure, returning a distinct semantic-validation reason when the JSON shape itself was valid.

### Validation
- Isolated Agent 2/3 valid and invalid-contract regression tests pass.
- Agent chain coverage verifies `Analyzer -> Agent 2 -> Agent 3 -> Agent 4`.

### Status
FIXED

## ALE-012 — Enforce mock contract and delayed generation

### Severity
HIGH

### Location
`ai_services/agents/agent4_mock_generator.py`, `ai_services/schemas/mock_schemas.py`, `ai_services/routers/mock.py`, `backend/server/src/controllers/exam.controller.js`, `backend/client/script.js`

### Problem
Mock generation did not require analyzer-derived weights for every target node, did not fully validate model-owned metadata and PYQ DNA, and could run when an exam was selected rather than when the learner entered the assessment.

### Solution
The Python request requires evidence-derived node weights and optional diagnostic weakness scores, never a fabricated default mastery value. Agent 4 now creates and validates test/question IDs, validates question count, node IDs, option quality, explanations, marks, time limit, and supplied PYQ references. API errors return a reason code with a specific status. The frontend starts a guarded request only when the Assessment panel opens.

### Validation
- Valid and invalid Agent 4 contract tests pass.
- Node syntax checks pass for the changed frontend/controller/API utility modules.

### Status
FIXED

## ALE-001 — Preserve document roles

### Severity
CRITICAL

### Location
`backend/server/src/controllers/exam.controller.js`, `backend/server/src/utils/ai-services.js`

### Problem
The Node service concatenated syllabus, PYQ, and notes into one blob and generated `GENERAL.*` nodes.

### Root cause
Document intelligence was implemented in the application orchestration layer.

### Impact
The analyzer received no real PYQ or notes evidence.

### Solution
Node now forwards separately typed multipart documents to Python and passes the returned `AnalyzerInput` unchanged to strategy generation.

### Files changed
- `backend/server/src/controllers/exam.controller.js`
- `backend/server/src/utils/ai-services.js`

### Validation
- Node syntax checks pass for both modules.
- The Python ingestion endpoint fixture verifies real node/PYQ/coverage payloads.

### Status
FIXED

## ALE-002 — Implement ingestion

### Severity
CRITICAL

### Location
`ai_services/routers/ingestion.py`

### Problem
`/ingest` returned a permanent uploaded status without processing documents.

### Root cause
The route was only a scaffold.

### Impact
No structured educational evidence reached the analyzer.

### Solution
The route now validates document size and extractability, extracts text/PDF content, parses source-derived syllabus nodes, PYQs, notes chunks, embeddings, coverage, and task status.

### Files changed
- `ai_services/routers/ingestion.py`
- `tests/test_pipeline_regression.py`

### Validation
- Endpoint fixture covers text upload, task completion, node/PYQ/chunk counts, and analyzer payload.

### Status
FIXED

## ALE-003 — Clarify analyzer contracts

### Severity
CRITICAL

### Location
`ai_services/schemas/analyzer_schemas.py`

### Problem
Nodes lacked explicit type and frequency represented question count rather than paper frequency.

### Root cause
Prototype schemas conflated different evidence measurements.

### Impact
Reports could misstate historical importance.

### Solution
Schemas now retain node type, PYQ source metadata, and separate `questions_asked`, `papers_appeared`, `years_appeared`, and normalized frequency.

### Files changed
- `ai_services/schemas/analyzer_schemas.py`
- `ai_services/agents/agent1_analyzer.py`

### Validation
- End-to-end fixture verifies a real 2024 PYQ, marks, and mapped topic.

### Status
FIXED

## ALE-004 — Deterministic analysis

### Severity
CRITICAL

### Location
`ai_services/agents/agent1_analyzer.py`

### Problem
An LLM could overwrite numerical analysis output.

### Root cause
Raw evidence and computed values shared one LLM output contract.

### Impact
Weightage, coverage, and ROI were not reproducible.

### Solution
Python owns all metrics and metadata. ROI is documented in the README and output carries explicit analysis status.

### Files changed
- `ai_services/agents/agent1_analyzer.py`
- `README.md`

### Validation
- The end-to-end fixture asserts deterministic non-zero ROI and successful status.

### Status
FIXED

## ALE-005 — Validate three report phases

### Severity
HIGH

### Location
`ai_services/agents/agent2_report_generator.py`

### Problem
Fallback reports could contain a variable number of phases and LLM output was accepted without phase validation.

### Root cause
Prompt constraints were not enforced in Python.

### Impact
The strategy contract could contradict the learner-facing plan.

### Solution
Fallback and accepted LLM reports require exactly the three named phases and known node references.

### Files changed
- `ai_services/agents/agent2_report_generator.py`

### Validation
- End-to-end fixture asserts phase count and all three headings.

### Status
FIXED

## ALE-006 — Replace hash vectors

### Severity
HIGH

### Location
`ai_services/stores/vector_store.py`

### Problem
The vector store used hash-based pseudo-vectors.

### Root cause
Prototype fallback code remained on the production path.

### Impact
Semantic retrieval and evidence coverage were unreliable.

### Solution
The store loads the configured 384-dimensional sentence-transformer model lazily, validates its dimension, and fails explicitly when unavailable.

### Files changed
- `ai_services/stores/vector_store.py`
- `ai_services/config.py`

### Validation
- Agent and endpoint tests load the configured model and exercise Qdrant retrieval.

### Status
FIXED

## ALE-009 — Reject fabricated mocks

### Severity
HIGH

### Location
`ai_services/agents/agent4_mock_generator.py`, `ai_services/routers/mock.py`

### Problem
Invalid or failed generation was normalized into generic academic questions.

### Root cause
The generator silently treated resilience fallback as valid learning content.

### Impact
Students could receive unrelated questions.

### Solution
Mock generation now requires analyzer-approved node IDs, strictly validates the complete output, and returns an explicit `503` failure when no validated model output is available.

### Files changed
- `ai_services/agents/agent4_mock_generator.py`
- `ai_services/routers/mock.py`
- `backend/server/src/controllers/exam.controller.js`

### Validation
- Focused smoke and agent tests assert the explicit unavailable path.

### Status
FIXED
