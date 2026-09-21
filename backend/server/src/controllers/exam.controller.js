import { asynchandler } from "../utils/asyncHandler.js";
import { Apierror } from "../utils/ApiError.js";
import { ApiResponse } from "../utils/ApiResponse.js";
import { Exam } from "../models/exam.model.js";
import { Chat } from "../models/chat.model.js";
import { MockTest } from "../models/mocktest.model.js";
import { uploadoncloudinary } from "../utils/cloudinary.js";
import { solveDoubt } from "../utils/gemini.js";
import { generateMock, generateStrategy, ingestExam } from "../utils/ai-services.js";

const extractMilestones = (markdown) => {
    const headings = [...String(markdown || "").matchAll(/^##\s+(.+)$/gm)];
    return headings.map((heading, index) => {
        const contentStart = heading.index + heading[0].length;
        const contentEnd = headings[index + 1]?.index ?? markdown.length;
        const description = markdown
            .slice(contentStart, contentEnd)
            .replace(/[>#*_`]/g, " ")
            .replace(/\s+/g, " ")
            .trim();
        return {
            title: heading[1].trim(),
            description: description.slice(0, 220) || "Follow the validated study tasks for this phase."
        };
    });
};

const toRoadmapStrategy = (strategyPlan, analyzerInput) => {
    const analysis = strategyPlan?.analysis || {};
    const markdown = strategyPlan?.report?.validated_markdown || strategyPlan?.draft?.markdown_body || "";
    const titlesByNodeId = new Map((analyzerInput?.syllabus_nodes || []).map((node) => [node.node_id, node.title]));
    const nodeScores = analysis.node_scores || [];

    return {
        ...strategyPlan,
        summary: `Validated evidence-backed roadmap for ${nodeScores.length} analyzed topic${nodeScores.length === 1 ? "" : "s"}.`,
        validated_markdown: markdown,
        milestones: extractMilestones(markdown),
        schedule: nodeScores.map((score, index) => ({
            day: index + 1,
            topic: titlesByNodeId.get(score.node_id) || score.node_id,
            tasks: [
                score.gap_flag ? "Review notes before practice." : "Complete focused concept review.",
                score.source_pyq_ids?.length ? `Practice ${score.source_pyq_ids.length} linked PYQ pattern${score.source_pyq_ids.length === 1 ? "" : "s"}.` : "Complete targeted practice questions."
            ]
        })),
        tips: [
            ...(analysis.critical_gaps || []).map((nodeId) => `Close the notes-coverage gap for ${titlesByNodeId.get(nodeId) || nodeId}.`),
            ...(analysis.top_roi_nodes || []).slice(0, 3).map((nodeId) => `Prioritize ${titlesByNodeId.get(nodeId) || nodeId} because it has high analyzer ROI.`)
        ]
    };
};

const setupExam = asynchandler(async (req, res) => {
    const { examName, duration, starttime, syllabusText, customInstruction } = req.body;
    const durationHours = Number(duration);

    if (
        !String(examName || "").trim()
        || String(examName).trim().length > 200
        || !Number.isFinite(durationHours)
        || durationHours <= 0
        || durationHours > 10_000
        || !/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(String(starttime || ""))
    ) {
        throw new Apierror(400, "Exam Name, Duration, and Start Time are required.");
    }
    if (typeof customInstruction !== "undefined" && (typeof customInstruction !== "string" || customInstruction.length > 5_000)) {
        throw new Apierror(400, "Custom instructions must be text no longer than 5,000 characters.");
    }
    if (Buffer.byteLength(String(syllabusText || ""), "utf8") > 10 * 1024 * 1024) {
        throw new Apierror(413, "Pasted syllabus text must be 10 MB or smaller.");
    }

    const syllabusUpload = req.files?.syllabus?.[0];
    const pyqUploads = req.files?.pyq || [];
    const noteUploads = req.files?.attachment || [];
    if (!syllabusUpload && !String(syllabusText || "").trim()) {
        throw new Apierror(400, "A syllabus file or syllabus text is required.");
    }

    const exam = new Exam({
        examName,
        duration: durationHours,
        starttime,
        syllabusText: syllabusText || "",
        customInstruction,
        owner: req.user._id
    });
    let syllabusFileUrl = "";
    let pyqFilesUrls = [];
    let notesFilesUrls = [];

    const ingestion = await ingestExam({
        examId: exam._id,
        examName,
        durationHours,
        syllabusText,
        syllabusFile: syllabusUpload,
        pyqFiles: pyqUploads,
        notesFiles: noteUploads,
        customInstructions: customInstruction
    });
    const strategyPlan = await generateStrategy({
        analyzerInput: ingestion.analyzer_input,
        customInstructions: customInstruction,
        docId: `strategy-${exam._id}`
    });

    if (syllabusUpload) {
        const cloudUpload = await uploadoncloudinary(syllabusUpload.path);
        if (cloudUpload) syllabusFileUrl = cloudUpload.secure_url;
    }
    for (const file of pyqUploads) {
        const cloudUpload = await uploadoncloudinary(file.path);
        if (cloudUpload) pyqFilesUrls.push(cloudUpload.secure_url);
    }
    for (const file of noteUploads) {
        const cloudUpload = await uploadoncloudinary(file.path);
        if (cloudUpload) notesFilesUrls.push(cloudUpload.secure_url);
    }
    exam.syllabusFile = syllabusFileUrl;
    exam.pyqFiles = pyqFilesUrls;
    exam.notesFiles = notesFilesUrls;
    exam.strategy = JSON.stringify(toRoadmapStrategy(strategyPlan, ingestion.analyzer_input));
    await exam.save();

    return res.status(201).json(
        new ApiResponse(201, exam, "Exam set up and study plan generated successfully")
    );
});

const getStrategy = asynchandler(async (req, res) => {
    const { examId } = req.params;
    const exam = await Exam.findOne({ _id: examId, owner: req.user._id });

    if (!exam) {
        throw new Apierror(404, "Exam not found or you do not have permission.");
    }

    let parsedStrategy;
    try {
        parsedStrategy = JSON.parse(exam.strategy);
    } catch (e) {
        parsedStrategy = { summary: exam.strategy };
    }

    return res.status(200).json(
        new ApiResponse(200, parsedStrategy, "Study strategy fetched successfully")
    );
});

const getChats = asynchandler(async (req, res) => {
    const { examId } = req.params;
    const chats = await Chat.find({ exam: examId, user: req.user._id }).sort({ createdAt: 1 });
    return res.status(200).json(
        new ApiResponse(200, chats, "Chat history fetched successfully")
    );
});

const getDoubts = asynchandler(async (req, res) => {
    const { examId } = req.params;
    const { doubt } = req.body;

    if (typeof doubt !== "string" || !doubt.trim() || doubt.length > 10_000) {
        throw new Apierror(400, "Doubt query is required");
    }

    const exam = await Exam.findOne({ _id: examId, owner: req.user._id });
    if (!exam) {
        throw new Apierror(404, "Exam not found");
    }

    const answer = await solveDoubt(doubt.trim(), exam.syllabusText, req.user._id, exam._id);

    return res.status(200).json(
        new ApiResponse(200, { answer }, "Doubt solved successfully")
    );
});

const getMockTest = asynchandler(async (req, res) => {
    const { examId } = req.params;
    const exam = await Exam.findOne({ _id: examId, owner: req.user._id });
    if (!exam) {
        throw new Apierror(404, "Exam not found");
    }

    // Check if mock test already exists
    let mockTest = await MockTest.findOne({ exam: examId, user: req.user._id });

    if (!mockTest) {
        console.log("Generating new mock exam via ai_services...");
        let strategy;
        try {
            strategy = JSON.parse(exam.strategy);
        } catch {
            throw new Apierror(422, "This exam has no valid analyzer output for mock generation.");
        }
        const analysis = strategy?.analysis;
        const targetNodeIds = analysis?.top_roi_nodes?.length
            ? analysis.top_roi_nodes
            : analysis?.node_scores?.map((score) => score.node_id).filter(Boolean).slice(0, 5);
        if (!targetNodeIds?.length) {
            throw new Apierror(422, "This exam has no analyzer-derived syllabus nodes for mock generation.");
        }
        const nodeWeights = Object.fromEntries(
            targetNodeIds.map((nodeId) => {
                const score = analysis.node_scores.find((item) => item.node_id === nodeId);
                return [nodeId, score?.roi_score || 0];
            })
        );
        if (!Object.values(nodeWeights).some((weight) => weight > 0)) {
            throw new Apierror(422, "This exam has no positive analyzer ROI evidence for mock generation.");
        }
        const sourcePyqRefs = [...new Set(
            (analysis?.node_scores || [])
                .filter((score) => targetNodeIds.includes(score.node_id))
                .flatMap((score) => score.source_pyq_ids || [])
        )];
        const generated = await generateMock({
            userId: req.user._id,
            mode: "exam_replica",
            questionCount: 5,
            timeLimitMinutes: 10,
            targetNodeIds,
            sourcePyqRefs,
            nodeWeights
        });
        const questions = generated.questions.map((question) => ({
            question: question.question_text,
            options: question.options,
            answer: String.fromCharCode(65 + question.correct_option_index),
            explanation: question.explanation
        }));
        mockTest = await MockTest.create({
            exam: examId,
            user: req.user._id,
            questions,
            score: 0,
            completed: false
        });
    }

    return res.status(200).json(
        new ApiResponse(200, mockTest, "Mock test fetched successfully")
    );
});

const submitMockTestScore = asynchandler(async (req, res) => {
    const { examId } = req.params;
    const { score } = req.body;
    const numericScore = Number(score);

    if (!Number.isFinite(numericScore) || numericScore < 0) {
        throw new Apierror(400, "Score must be a non-negative number.");
    }

    const mockTest = await MockTest.findOne({ exam: examId, user: req.user._id });

    if (!mockTest) {
        throw new Apierror(404, "Mock test not found");
    }
    if (numericScore > mockTest.questions.length) {
        throw new Apierror(400, "Score cannot exceed the number of mock questions.");
    }

    mockTest.score = numericScore;
    mockTest.completed = true;
    await mockTest.save();

    return res.status(200).json(
        new ApiResponse(200, mockTest, "Mock test score submitted successfully")
    );
});

const getExamsList = asynchandler(async (req, res) => {
    const exams = await Exam.find({ owner: req.user._id }).sort({ createdAt: -1 });
    return res.status(200).json(
        new ApiResponse(200, exams, "Exams list fetched successfully")
    );
});

export {
    setupExam,
    getStrategy,
    getChats,
    getDoubts,
    getMockTest,
    submitMockTestScore,
    getExamsList
};
