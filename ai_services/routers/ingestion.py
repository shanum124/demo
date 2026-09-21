import io
import json
import re
from collections.abc import Iterable
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
import pdfplumber

from ai_services.schemas.analyzer_schemas import AnalyzerInput, DifficultyTag, NotesCoverageItem, PYQIndexItem, SyllabusNode

router = APIRouter()
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
_tasks: dict[str, dict] = {}
_bridge = None
_extractor = None


def _tokenize(text: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if len(token) <= 2:
            continue
        tokens.add(token)
        if token.endswith("s") and len(token) > 3:
            tokens.add(token[:-1])
    return tokens


def _normalize_text(text: str) -> str:
    return "\n".join(re.sub(r"\s+", " ", line).strip() for line in text.replace("\x00", "").splitlines() if line.strip())


def _extract_text(filename: str, raw: bytes) -> str:
    if not raw:
        raise ValueError(f"{filename}: document is empty")
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError(f"{filename}: exceeds the {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB processing limit")
    if filename.lower().endswith(".pdf") or raw.startswith(b"%PDF"):
        with pdfplumber.open(io.BytesIO(raw)) as document:
            text = "\n".join(page.extract_text() or "" for page in document.pages)
    else:
        text = raw.decode("utf-8", errors="strict")
    normalized = _normalize_text(text)
    if not normalized:
        raise ValueError(f"{filename}: no extractable text was found")
    return normalized


async def _read_document(upload: UploadFile) -> tuple[str, str]:
    try:
        raw = await upload.read()
        return upload.filename or "document", _extract_text(upload.filename or "document", raw)
    except (UnicodeDecodeError, ValueError, pdfplumber.PDFSyntaxError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def parse_syllabus_structure(raw_text: str) -> list[SyllabusNode]:
    text = (raw_text or "").strip()
    if not text:
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    nodes: list[SyllabusNode] = []
    topic_index = 0
    current_unit_id: str | None = None

    def add_topic(title: str, parent_id: str | None = None, prefix: str = "TOPIC") -> None:
        nonlocal topic_index
        node_id = f"{parent_id}.{prefix}.{topic_index + 1}" if parent_id else f"{prefix}.{topic_index + 1}"
        nodes.append(SyllabusNode(node_id=node_id, title=title, parent_id=parent_id, node_type="topic"))
        topic_index += 1

    for line in lines:
        unit_match = re.match(r"^(?:UNIT|MODULE|CHAPTER|PART)\s*[:#-]?\s*(\d+)\s*(?:[:\-–]\s*)?(.*)$", line, flags=re.IGNORECASE)
        if unit_match:
            topic_index = 0
            unit_no = unit_match.group(1)
            unit_title = (unit_match.group(2) or f"Unit {unit_no}").strip()
            current_unit_id = f"UNIT.{unit_no}"
            nodes.append(SyllabusNode(node_id=current_unit_id, title=unit_title, parent_id=None, node_type="unit"))
            continue

        topic_match = re.match(r"^(?:TOPIC|SUBTOPIC|SECTION|CONCEPT)\s*[:\-–]?\s*(.+)$", line, flags=re.IGNORECASE)
        if topic_match:
            title = topic_match.group(1).strip()
            if current_unit_id:
                add_topic(title, current_unit_id, "TOPIC")
            else:
                add_topic(title, None, "TOPIC")
            continue

        if re.match(r"^\d+[\.)\-:]\s*.+$", line):
            title = re.sub(r"^\d+[\.)\-:]\s*", "", line).strip()
            if current_unit_id:
                add_topic(title, current_unit_id, "TOPIC")
            else:
                add_topic(title, None, "TOPIC")
            continue

        if current_unit_id and len(line) > 2:
            add_topic(line, current_unit_id, "TOPIC")

    if not nodes:
        for idx, line in enumerate(lines, start=1):
            title = re.sub(r"^[\-*•\s]+", "", line)
            if title:
                nodes.append(SyllabusNode(node_id=f"TOPIC.{idx}", title=title, parent_id=None, node_type="topic"))

    deduped: list[SyllabusNode] = []
    seen: set[str] = set()
    for node in nodes:
        if node.node_id in seen:
            continue
        seen.add(node.node_id)
        deduped.append(node)
    return deduped


def _match_node_ids(text: str, syllabus_nodes: Iterable[SyllabusNode], semantic_ranker=None) -> list[str]:
    candidates = [node for node in syllabus_nodes if node.node_type != "unit"]
    text_tokens = _tokenize(text)
    scored = []
    for node in candidates:
        overlap = len(text_tokens & _tokenize(node.title))
        if overlap:
            scored.append((overlap, node.node_id))
    if scored:
        best_overlap = max(score for score, _ in scored)
        return [node_id for score, node_id in scored if score == best_overlap]
    if semantic_ranker is None or not candidates:
        return []
    similarities = semantic_ranker(text, [node.title for node in candidates])
    if not similarities:
        return []
    best_score = max(similarities)
    if best_score < 0.35:
        return []
    return [node.node_id for node, score in zip(candidates, similarities) if score == best_score]


def _extract_difficulty(text: str) -> DifficultyTag | None:
    match = re.search(r"\b(easy|medium|hard)\b", text, flags=re.IGNORECASE)
    return DifficultyTag(match.group(1).lower()) if match else None


def parse_pyq_documents(documents: list[tuple[str, str]], syllabus_nodes: list[SyllabusNode], semantic_ranker=None) -> list[PYQIndexItem]:
    question_boundary = re.compile(r"(?im)^\s*(?:q(?:uestion)?\s*)?(\d+)\s*(?:[.)]|:)\s*")
    pyqs: list[PYQIndexItem] = []
    for filename, text in documents:
        years = re.findall(r"\b(20\d{2})\b", text)
        year = int(years[0]) if years else None
        sections = question_boundary.split(text)
        for index in range(1, len(sections), 2):
            question_number = sections[index]
            question_text = sections[index + 1]
            clean_text = _normalize_text(question_text)
            if not clean_text:
                continue
            marks_match = re.search(r"\[?\s*(\d+(?:\.\d+)?)\s*marks?\s*\]?", clean_text, flags=re.IGNORECASE)
            marks = float(marks_match.group(1)) if marks_match else None
            node_ids = _match_node_ids(clean_text, syllabus_nodes, semantic_ranker)
            node_titles = [node.title for node in syllabus_nodes if node.node_id in node_ids]
            pyqs.append(PYQIndexItem(
                pyq_id=f"{uuid4().hex}",
                node_ids=node_ids,
                year=year,
                marks=marks,
                difficulty_tag=_extract_difficulty(clean_text),
                question_number=question_number,
                source_document=filename,
                dna_tags=node_titles,
            ))
    return pyqs


def chunk_notes_documents(documents: list[tuple[str, str]], syllabus_nodes: list[SyllabusNode], exam_id: str, semantic_ranker=None, chunk_words: int = 180, overlap_words: int = 30) -> list[dict]:
    chunks: list[dict] = []
    for filename, text in documents:
        words = text.split()
        for start in range(0, len(words), max(1, chunk_words - overlap_words)):
            segment = " ".join(words[start:start + chunk_words]).strip()
            if not segment:
                continue
            node_ids = _match_node_ids(segment, syllabus_nodes, semantic_ranker)
            chunks.append({
                "chunk_id": f"note-{uuid4().hex}",
                "source_doc_id": filename,
                "exam_id": exam_id,
                "node_id": node_ids[0] if node_ids else "",
                "text": segment,
                "section": None,
                "page": None,
            })
            if start + chunk_words >= len(words):
                break
    return chunks


def calculate_notes_coverage(syllabus_nodes: list[dict] | list[SyllabusNode], note_chunks: list[dict]) -> dict[str, float]:
    if not syllabus_nodes:
        return {}

    coverage_map: dict[str, float] = {}
    chunk_lookup: dict[str, list[str]] = {}
    for chunk in note_chunks:
        chunk_lookup.setdefault(str(chunk.get("node_id") or ""), []).append(str(chunk.get("text") or ""))

    for node in syllabus_nodes:
        if isinstance(node, dict):
            node_id = str(node.get("node_id", ""))
            title = str(node.get("title", ""))
        else:
            node_id = node.node_id
            title = node.title
        title_tokens = _tokenize(title)
        direct_hits = chunk_lookup.get(node_id, [])
        relevant_chunks = direct_hits[:]
        for chunk in note_chunks:
            chunk_text = str(chunk.get("text") or "")
            if chunk.get("node_id") == node_id:
                continue
            if title_tokens and _tokenize(chunk_text) & title_tokens:
                relevant_chunks.append(chunk_text)
        # A node is fully covered once three distinct, relevant chunks are indexed.
        score = min(1.0, len({chunk for chunk in relevant_chunks if chunk}) / 3)
        coverage_map[node_id] = round(max(0.0, min(1.0, score)), 4)
    return coverage_map


async def calculate_semantic_notes_coverage(syllabus_nodes: list[SyllabusNode], note_chunks: list[dict], exam_id: str) -> dict[str, float]:
    if not note_chunks:
        return {node.node_id: 0.0 for node in syllabus_nodes}
    if _bridge is None:
        return calculate_notes_coverage(syllabus_nodes, note_chunks)
    coverage: dict[str, float] = {}
    for node in syllabus_nodes:
        results = await _bridge.vector.search(node.title, top_k=3, exam_id=exam_id)
        relevant_chunk_ids = {result.chunk_id for result in results if result.score >= 0.35}
        coverage[node.node_id] = round(min(1.0, len(relevant_chunk_ids) / 3), 4)
    return coverage


def _persist_ingestion(analyzer_input: AnalyzerInput, note_chunks: list[dict]) -> None:
    if _bridge is None:
        return
    _bridge.syllabus.put_nodes([node.model_dump() for node in analyzer_input.syllabus_nodes])
    for pyq in analyzer_input.pyq_index:
        _bridge.pyqs.put({
            "pyq_id": pyq.pyq_id,
            "node_ids": pyq.node_ids,
            "year": pyq.year,
            "marks": pyq.marks,
            "difficulty_tag": pyq.difficulty_tag.value if pyq.difficulty_tag else None,
            "dna_tags": pyq.dna_tags,
            "full_text": "",
        })


def configure(bridge, extractor):
    global _bridge, _extractor
    _bridge = bridge
    _extractor = extractor
    return router


@router.post("/ingest")
async def ingest(
    syllabus: UploadFile = File(...),
    pyqs: list[UploadFile] = File(default=[]),
    notes: list[UploadFile] = File(default=[]),
    exam_name: str = Form(...),
    exam_timing_weeks: int = Form(...),
    exam_id: str | None = Form(None),
    custom_instructions: str = Form("[]"),
):
    if not exam_name.strip():
        raise HTTPException(status_code=422, detail="exam_name must not be empty")
    if not 1 <= exam_timing_weeks <= 520:
        raise HTTPException(status_code=422, detail="exam_timing_weeks must be between 1 and 520")
    try:
        parsed_instructions = json.loads(custom_instructions)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="custom_instructions must be a JSON array of strings") from exc
    if not isinstance(parsed_instructions, list) or any(not isinstance(item, str) for item in parsed_instructions):
        raise HTTPException(status_code=422, detail="custom_instructions must be a JSON array of strings")
    extracted_request = await _extractor.extract_ingestion_request(
        exam_name,
        exam_timing_weeks,
        parsed_instructions,
    )
    task_id = str(uuid4())
    scope_id = exam_id or task_id
    _tasks[task_id] = {"task_id": task_id, "state": "EXTRACTING", "progress": 0.1}
    syllabus_document = await _read_document(syllabus)
    pyq_documents = [await _read_document(upload) for upload in pyqs]
    note_documents = [await _read_document(upload) for upload in notes]

    _tasks[task_id].update(state="PARSING_SYLLABUS", progress=0.3)
    syllabus_nodes = parse_syllabus_structure(syllabus_document[1])
    if not syllabus_nodes:
        _tasks[task_id].update(state="FAILED", error="No syllabus nodes could be extracted")
        raise HTTPException(status_code=422, detail="No syllabus nodes could be extracted from the uploaded syllabus")

    _tasks[task_id].update(state="PARSING_PYQS", progress=0.5)
    semantic_ranker = _bridge.vector.rank_texts if _bridge is not None else None
    pyq_index = parse_pyq_documents(pyq_documents, syllabus_nodes, semantic_ranker)
    _tasks[task_id].update(state="PROCESSING_NOTES", progress=0.7)
    note_chunks = chunk_notes_documents(note_documents, syllabus_nodes, scope_id, semantic_ranker)
    _tasks[task_id].update(state="BUILDING_INDEX", progress=0.85)
    if _bridge is not None and note_chunks:
        await _bridge.vector.ingest(note_chunks)
    coverage = await calculate_semantic_notes_coverage(syllabus_nodes, note_chunks, scope_id)
    analyzer_input = AnalyzerInput(
        exam_id=scope_id,
        exam_name=extracted_request.exam_name,
        exam_timing_weeks=extracted_request.exam_timing_weeks,
        syllabus_nodes=syllabus_nodes,
        pyq_index=pyq_index,
        notes_coverage_map=[
            NotesCoverageItem(
                node_id=node.node_id,
                chunk_ids=[chunk["chunk_id"] for chunk in note_chunks if chunk["node_id"] == node.node_id],
                coverage_score=coverage[node.node_id],
            )
            for node in syllabus_nodes
        ],
    )
    extracted = await _extractor.extract_ingestion(analyzer_input, extracted_request.custom_instructions)
    analyzer_input = extracted.analyzer_input
    parsed_instructions = extracted.custom_instructions
    _persist_ingestion(analyzer_input, note_chunks)

    _tasks[task_id].update(state="COMPLETED", progress=1.0)
    return {
        "task_id": task_id,
        "status": "COMPLETED",
        "analyzer_input": analyzer_input,
        "document_counts": {"syllabus": 1, "pyqs": len(pyq_documents), "notes": len(note_documents), "note_chunks": len(note_chunks)},
        "custom_instructions": parsed_instructions,
        "extraction": {"request": extracted_request.metadata, "agent_input": extracted.metadata},
    }


@router.get("/ingest/status/{task_id}")
async def status(task_id: str):
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Ingestion task not found")
    return task
