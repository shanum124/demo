# Browser, Backend, and AI-service API Contract

This is the runtime contract for the current pipeline. The browser only calls
the Node API. Node owns authentication and MongoDB records; FastAPI owns
document intelligence and validated generation. Agent 0, the typed input
extractor, receives each FastAPI request before the downstream learning agent.
It preserves validated syllabus/PYQ/notes evidence, normalizes free-text
instructions, and emits the JSON model consumed by that agent. The frontend may be served by
Node on port `8002` or by `npm run client` on port `5000`; in both cases local
API and Socket.IO requests target port `8002`.

## Browser to Node API

All Node responses use this envelope:

```json
{ "success": true, "statusCode": 200, "message": "...", "data": {} }
```

| Browser request | Required input | Successful `data` output | Downstream action |
| --- | --- | --- | --- |
| `POST /api/v1/users/register` | JSON: `username`, `email`, `password` | user | creates account |
| `POST /api/v1/users/login` | JSON: `username` **or** `email`, `password` | `user`, `accessToken`, `refreshToken` | browser stores token |
| `POST /api/v1/users/guest-login` | none | `user`, `accessToken`, `refreshToken` | browser stores token |
| `GET /api/v1/users/me` | Bearer token | user | restores session |
| `POST /api/v1/users/refresh-token` | refresh-token cookie or JSON `refreshToken` | `accessToken`, `refreshToken` | renews a session |
| `POST /api/v1/users/logout` | Bearer token | `{}` | clears the stored session |
| `GET /api/v1/exams/list` | Bearer token | exam array | selects and renders saved roadmap |
| `POST /api/v1/exams/setup` | multipart: `examName`, `duration` (hours), `starttime` (`HH:mm`), plus a `syllabus` file or `syllabusText`; optional `pyq` and `attachment` files, `customInstruction` | saved exam, including serialized `strategy` | calls FastAPI ingestion then strategy generation |
| `GET /api/v1/exams/strategy/:examId` | Bearer token, owned `examId` | normalized roadmap strategy | renders roadmap |
| `POST /api/v1/exams/doubt/:examId` | JSON: `doubt` | `{ "answer": "Markdown" }` | scopes chat retrieval to the exam |
| `GET /api/v1/exams/mock/:examId` | Bearer token, owned `examId` | saved validated mock test | requests FastAPI mock generation when none exists |
| `POST /api/v1/exams/mock/:examId/submit` | JSON: numeric `score` | updated mock test | saves completion |
| `GET /api/v1/exams/chat/:examId` | Bearer token | chat-message array | loads history |

The Node API owns the envelope. Browser code must read all successful payloads
from `response.data`, not from the top level. It must surface `response.message`
when `response.success` is `false`.

`duration` remains the browser's preparation-window hours. Node derives the
AI service's `exam_timing_weeks` as `max(1, ceil(duration / 7))`; this is a
planning bucket, not a claim that the user has seven hours every calendar week.

## Node to FastAPI

| FastAPI request | Exact Node input | FastAPI output consumed by Node |
| --- | --- | --- |
| `POST /ingest` | multipart: `exam_id`, `exam_name`, `exam_timing_weeks`, JSON-string `custom_instructions`, exactly one `syllabus`, zero or more `pyqs`, zero or more `notes` | `status: "COMPLETED"`, `analyzer_input`, `document_counts` |
| `POST /strategy/generate` | JSON: `analyzer_input` returned unchanged from `/ingest`, `custom_instructions`, `doc_id` | `analysis`, `draft`, `report` |
| `POST /chat` | JSON: `user_id`, `message`, optional `thread_id`, optional `exam_id` | `assistant_response`, `intent_class`, `action`, `profile_delta` |
| `POST /mock/generate` | JSON: `user_id`, `mode`, `question_count`, `time_limit_minutes`, `target_node_ids`, `source_pyq_refs`, `node_weights`, optional `weakness_scores` | validated `MockTest` |

Before downstream processing, Agent 0 builds these internal JSON inputs:

| Downstream agent | Extracted JSON input |
| --- | --- |
| Ingestion parser | normalized `exam_name`, `exam_timing_weeks`, and deduplicated `custom_instructions` before document extraction |
| Analyzer | validated `AnalyzerInput` plus deduplicated `custom_instructions` |
| Report generator/editor | validated `AnalyzerInput`, normalized instructions, non-empty `doc_id` |
| Orchestrator | validated `OrchestratorInput` with normalized learner message |
| Mock generator | validated `MockGeneratorInput` with deduplicated node and PYQ identifiers |

Agent 0 does not create or alter syllabus nodes, PYQ evidence, notes coverage,
node weights, learner identifiers, or exam identifiers. Set
`ALE_EXTRACTOR_USE_LLM=true` to enable LLM normalization of free-text custom
instructions; it falls back to deterministic normalization if the LLM is
unavailable or invalid.

## FastAPI Service Endpoints

These routes are internal service APIs. The browser must not call them directly;
Node is the boundary for learner requests and authentication.

| FastAPI request | Required input | Successful output | Current caller |
| --- | --- | --- | --- |
| `GET /health` | none | `status`, `environment` | deployment health check |
| `POST /ingest` | multipart: `syllabus`, `exam_name`, `exam_timing_weeks`; optional `exam_id`, repeated `pyqs`, repeated `notes`, JSON-string `custom_instructions` | `task_id`, `status`, `analyzer_input`, `document_counts`, `custom_instructions` | Node setup adapter |
| `GET /ingest/status/:taskId` | `taskId` | `task_id`, `state`, `progress`, optional `error` | internal polling only |
| `POST /strategy/generate` | JSON: `analyzer_input`, optional `custom_instructions`, `doc_id` | `analysis`, `draft`, `report` | Node setup adapter |
| `POST /chat` | JSON: `user_id`, `message`; optional `thread_id`, `exam_id` | `intent_class`, `action`, `assistant_response`, `profile_delta` | Node Socket.IO chat adapter |
| `POST /doubt` | same as `/chat` | same as `/chat` | available internally; Node uses `/chat` |
| `POST /mock/generate` | JSON: `user_id`, `mode`, `question_count`, `time_limit_minutes`, non-empty `target_node_ids`, complete `node_weights`; optional `source_pyq_refs`, `weakness_scores` | `test_id`, `mode`, `questions`, `total_marks`, `time_limit_minutes` | Node mock adapter |
| `POST /mock/submit` | JSON: `test_id`, `user_id`, `per_question_results`, `total_time_s` | `score`, `test_id` | available internally; Node persists its browser score independently |
| `GET /report` | query `doc_id` (default `strategy`) | `doc_id`, `markdown` | internal report retrieval |
| `PATCH /report` | query `doc_id`; JSON `section`, `patch` | `version` | internal report editing |
| `GET /profile/:userId` | `userId` | semantic profile | internal profile read |
| `GET /telemetry/:userId` | `userId` | `events` array | internal telemetry read |

## Output Invariants

`/strategy/generate` must always return a non-empty
`draft.markdown_body` and `report.validated_markdown`. If the configured model
cannot produce a schema-valid report, Agents 2 and 3 return a deterministic
fallback with `generation_status: "deterministic_fallback"` instead of a false
successful empty response. Node converts that response to the browser-ready
`summary`, `validated_markdown`, `milestones`, `schedule`, and `tips` fields.

The Node setup controller persists a browser-ready projection of the strategy:
`summary`, `validated_markdown`, `milestones`, `schedule`, and `tips`, while
retaining `analysis`, `draft`, and `report` for traceability. Mock generation
only accepts node IDs and weights that originated in `analysis`; it does not
fabricate generic questions if the model is unavailable.

## Realtime chat event contract

| Event | Direction | Payload |
| --- | --- | --- |
| `send-message` | browser -> Node | `{ examId, message }` |
| `chat-stream-start` | Node -> browser | none |
| `chat-stream-chunk` | Node -> browser | `{ text: "..." }` |
| `chat-stream-end` | Node -> browser | saved model chat message |
| `chat-stream-error` | Node -> browser | `{ error: "..." }` |

The browser normalizes the chunk payload to its `text` field before rendering.
It therefore no longer writes `[object Object]` into the chat view.

## Validated runtime variables

| Variable | Owner | Required value |
| --- | --- | --- |
| `PORT` | Node | Node API port; default `8002` |
| `MONGODB_URI` | Node | MongoDB base connection URI |
| `ACCESS_TOKEN_SECRET`, `REFRESH_TOKEN_SECRET` | Node | non-empty signing secrets |
| `AI_SERVICES_URL` | Node | reachable FastAPI base URL, normally `http://127.0.0.1:8001` |
| `AI_SERVICES_ENABLED` | Node | `true` for the current evidence-backed setup/mock pipeline |
| `ALE_OLLAMA_MODEL` | FastAPI | model capable of validated report/mock JSON when generation is needed |
| `ALE_EMBEDDING_MODEL` | FastAPI | `sentence-transformers/all-MiniLM-L6-v2` by default |
| `ALE_EMBEDDING_DIMENSION` | FastAPI | must match the model dimension and Qdrant collection; default `384` |
| `ALE_EMBEDDING_LOCAL_FILES_ONLY` | FastAPI | `true` by default; pre-cache the embedding model in the runtime image |
| `ALE_QDRANT_URL` / `ALE_QDRANT_DIR` | FastAPI | use one Qdrant server URL for concurrent workers, or one local process for the local directory |

When FastAPI rejects a request, Node preserves its HTTP status and meaningful
validation message in the browser response. Individual uploads are limited to
10 MB at both the Node multipart boundary and FastAPI extraction boundary.
