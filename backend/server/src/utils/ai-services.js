import { Blob } from "node:buffer";
import { readFile } from "node:fs/promises";

const AI_SERVICES_URL = () => (process.env.AI_SERVICES_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

class AIServiceError extends Error {
    constructor(status, message, detail = null) {
        super(message);
        this.name = "AIServiceError";
        this.statusCode = status >= 400 && status < 600 ? status : 502;
        this.detail = detail;
    }
}

const responseBody = async (response) => {
    const raw = await response.text();
    if (!raw) return null;
    try {
        return JSON.parse(raw);
    } catch {
        return raw;
    }
};

const errorMessage = (body, fallback) => {
    if (typeof body === "string") return body || fallback;
    if (Array.isArray(body?.detail)) return body.detail.map((item) => item.msg || item.message || String(item)).join("; ");
    if (typeof body?.detail === "object") return body.detail.message || body.detail.reason || fallback;
    return body?.detail || body?.message || fallback;
};

const postJson = async (path, body) => {
    let response;
    try {
        response = await fetch(`${AI_SERVICES_URL()}${path}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
    } catch (error) {
        throw new AIServiceError(503, `AI service is unreachable at ${AI_SERVICES_URL()}. Start the FastAPI service and retry.`);
    }
    const result = await responseBody(response);
    if (!response.ok) {
        throw new AIServiceError(response.status, errorMessage(result, `AI service rejected ${path}.`), result);
    }
    return result;
};

export const generateDoubtAnswer = async (userId, message, threadId, examId) => {
    const result = await postJson("/chat", {
        user_id: String(userId || "guest"),
        message,
        thread_id: threadId,
        exam_id: examId ? String(examId) : null
    });
    return result.assistant_response || result.response || "Unable to process doubt.";
};

export const generateMock = async ({ userId, mode, questionCount, timeLimitMinutes, targetNodeIds, sourcePyqRefs = [], nodeWeights, weaknessScores = {} }) => {
    if (!targetNodeIds?.length) {
        throw new Error("Mock generation requires analyzer-derived target node IDs.");
    }
    if (!nodeWeights || targetNodeIds.some((nodeId) => typeof nodeWeights[nodeId] !== "number")) {
        throw new Error("Mock generation requires evidence-derived weights for every target node.");
    }
    return postJson("/mock/generate", {
        user_id: String(userId || "guest"),
        mode: mode === "diagnostic_drill" ? "diagnostic_drill" : "exam_replica",
        question_count: questionCount,
        time_limit_minutes: timeLimitMinutes,
        target_node_ids: targetNodeIds,
        source_pyq_refs: sourcePyqRefs,
        node_weights: nodeWeights,
        weakness_scores: weaknessScores
    });
};

export const generateChatAnswer = async (userId, message, threadId, examId) => {
    return generateDoubtAnswer(userId, message, threadId, examId);
};

const appendUpload = async (form, field, upload) => {
    if (!upload?.path) return;
    const bytes = await readFile(upload.path);
    form.append(field, new Blob([bytes], { type: upload.mimetype || "application/octet-stream" }), upload.originalname);
};

export const ingestExam = async ({ examId, examName, durationHours, syllabusText, syllabusFile, pyqFiles = [], notesFiles = [], customInstructions }) => {
    const form = new FormData();
    form.append("exam_id", String(examId));
    form.append("exam_name", examName);
    form.append("exam_timing_weeks", String(Math.max(1, Math.ceil(Number(durationHours) / 7))));
    form.append("custom_instructions", JSON.stringify(customInstructions ? [String(customInstructions)] : []));
    if (syllabusFile?.path) {
        await appendUpload(form, "syllabus", syllabusFile);
    } else if (String(syllabusText || "").trim()) {
        form.append("syllabus", new Blob([syllabusText], { type: "text/plain" }), "inline-syllabus.txt");
    } else {
        throw new Error("A syllabus file or syllabus text is required for ingestion.");
    }
    for (const file of pyqFiles) await appendUpload(form, "pyqs", file);
    for (const file of notesFiles) await appendUpload(form, "notes", file);
    let response;
    try {
        response = await fetch(`${AI_SERVICES_URL()}/ingest`, { method: "POST", body: form });
    } catch (error) {
        throw new AIServiceError(503, `AI service is unreachable at ${AI_SERVICES_URL()}. Start the FastAPI service and retry.`);
    }
    const result = await responseBody(response);
    if (!response.ok) {
        throw new AIServiceError(response.status, errorMessage(result, "AI ingestion failed."), result);
    }
    return result;
};

export const generateStrategy = async ({ analyzerInput, customInstructions, docId }) => {
    if (!analyzerInput?.syllabus_nodes?.length) {
        throw new Error("Cannot generate a strategy without parsed syllabus nodes.");
    }
    return postJson("/strategy/generate", {
        analyzer_input: analyzerInput,
        custom_instructions: customInstructions ? [String(customInstructions)] : [],
        doc_id: docId || `strategy-${analyzerInput.exam_id || analyzerInput.exam_name}`
    });
};
