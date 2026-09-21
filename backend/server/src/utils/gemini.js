import Groq from "groq-sdk";
import { generateChatAnswer, generateDoubtAnswer, generateMock, generateStrategy } from "./ai-services.js";

let groqClient = null;

// Lazy-init Groq client
const getGroq = () => {
    if (!groqClient) {
        const key = process.env.GROQ_API_KEY;
        if (!key) throw new Error("GROQ_API_KEY is missing from environment variables.");
        groqClient = new Groq({ apiKey: key });
    }
    return groqClient;
};

const MODEL = "llama-3.3-70b-versatile"; // 14,400 req/day free — 24x7 reliable

/**
 * Compatibility facade for AI generation. Primary calls go through ai_services.
 */
export const generateStudyStrategy = async (examName, duration, starttime, syllabusText, customInstructions) => {
    const prompt = `You are an expert academic tutor and study coordinator. Create a highly structured study plan/strategy for the exam: "${examName}".

Details:
- Total study hours available: ${duration} hours
- Study start time: ${starttime}
- Custom user guidelines: ${customInstructions || "None"}

Syllabus/Materials:
"""
${syllabusText || "No syllabus provided. Create a general standard syllabus for this subject."}
"""

Return ONLY valid JSON (no markdown fences, no extra text) matching this EXACT schema:
{
  "summary": "Expert 2-3 sentence strategy to crack this exam",
  "milestones": [
    { "title": "Phase title", "description": "What to achieve", "percentage": 30 }
  ],
  "schedule": [
    { "day": "Day 1", "topic": "Topic Name", "tasks": ["Task 1", "Task 2"], "durationHours": 2 }
  ],
  "tips": ["Tip 1", "Tip 2", "Tip 3"]
}

Requirements:
- Create milestones covering Foundation, Practice, Revision phases
- Create a day-by-day schedule proportional to ${duration} total hours
- Each day should have 2-4 tasks
- Tips should be actionable and specific
- Keep tone professional, no emojis`;

    try {
        if (process.env.AI_SERVICES_ENABLED !== "false") {
            return await generateStrategy({ examName, durationHours: duration, syllabusText, customInstructions });
        }
        const groq = getGroq();
        const completion = await groq.chat.completions.create({
            model: MODEL,
            messages: [{ role: "user", content: prompt }],
            temperature: 0.7,
            max_tokens: 3000,
            response_format: { type: "json_object" }
        });
        const text = completion.choices[0]?.message?.content || "{}";
        return JSON.parse(text);
    } catch (error) {
        console.error("Error in generateStudyStrategy:", error.message);
        // Smart fallback based on syllabus content
        const hoursPerPhase = Math.ceil(duration / 3);
        return {
            summary: `To succeed in ${examName}, divide your ${duration} hours into structured phases: foundation building, practice, and final revision. Prioritize active recall and timed practice sessions.`,
            milestones: [
                { title: "Foundation Phase", description: "Build core concepts and read all syllabus topics systematically.", percentage: 35 },
                { title: "Practice & Application", description: "Solve previous year questions and apply concepts to problems.", percentage: 70 },
                { title: "Revision & Mock Tests", description: "Take full-length mock exams, revise weak areas, review key formulas.", percentage: 100 }
            ],
            schedule: [
                { day: "Day 1-2", topic: "Syllabus Overview & Core Concepts", tasks: ["Read all syllabus topics", "Make chapter-wise notes", "Identify high-weightage areas"], durationHours: hoursPerPhase },
                { day: "Day 3-4", topic: "Deep Dive & Problem Solving", tasks: ["Solve standard textbook problems", "Work on previous year papers", "Use Doubt Solver for unclear topics"], durationHours: hoursPerPhase },
                { day: "Day 5", topic: "Mock Exams & Final Revision", tasks: ["Take timed mock test", "Review all incorrect answers", "Revise key formulas and definitions"], durationHours: Math.ceil(duration * 0.2) }
            ],
            tips: [
                "Use the Pomodoro technique: 25 min study, 5 min break.",
                "After each topic, close the book and recall key points aloud.",
                "Solve the Mock Exam daily — it trains your brain for exam conditions.",
                "Use the Doubt Solver immediately when a concept is unclear — don't skip it."
            ]
        };
    }
};

/**
 * Solves a student doubt with professional Markdown explanation
 */
export const solveDoubt = async (doubtText, syllabusText, userId = "guest", examId = undefined) => {
    const prompt = `You are a highly skilled academic tutor. Provide a detailed, professional, and structured explanation for this student's doubt.

Syllabus context:
"""
${syllabusText ? syllabusText.substring(0, 3000) : "General academics"}
"""

Student's Doubt:
"""
${doubtText}
"""

Instructions:
- Use professional Markdown formatting (headers, bullet points, numbered steps)
- Include code blocks for algorithms or pseudocode where relevant
- Use mathematical notation for formulas
- Be thorough but clear — explain step by step
- Provide a worked example if it helps understanding
- Do NOT use emojis, casual language, or filler phrases`;

    try {
        if (process.env.AI_SERVICES_ENABLED !== "false") {
            return await generateDoubtAnswer(userId, doubtText, undefined, examId);
        }
        const groq = getGroq();

        const completion = await groq.chat.completions.create({
            model: MODEL,
            messages: [{ role: "user", content: prompt }],
            temperature: 0.5,
            max_tokens: 2000
        });
        return completion.choices[0]?.message?.content || "Unable to process doubt. Please try again.";
    } catch (error) {
        console.error("Error in solveDoubt:", error.message);
        return `## Doubt Analysis\n\nYour question: **${doubtText.substring(0, 80)}...**\n\n**Note:** The AI service is temporarily unavailable. Please check that ai_services is running, then try again.\n\n### Quick Study Tips While You Wait:\n1. Consult your course textbook for this topic\n2. Break the problem into smaller sub-questions\n3. Look for similar solved examples in your notes`;
    }
};

/**
 * Generates MCQ questions for Mock Exam
 */
export const generateMockExamQuestions = async (syllabusText, numQuestions = 5) => {
    const prompt = `You are an expert exam question designer for competitive and university exams.

Syllabus/Context:
"""
${syllabusText ? syllabusText.substring(0, 3000) : "General computer science and engineering topics"}
"""

Generate exactly ${numQuestions} high-quality multiple choice questions. Return ONLY valid JSON array (no markdown fences):
[
  {
    "question": "Clear, specific question text?",
    "options": ["A) Option text", "B) Option text", "C) Option text", "D) Option text"],
    "answer": "A",
    "explanation": "Why this answer is correct — explain the concept clearly."
  }
]

Requirements:
- Questions must be directly from the syllabus content provided
- Mix difficulty levels: 2 easy, 2 medium, 1 hard
- "answer" field must be exactly one of: "A", "B", "C", "D"
- Explanations must be educational and 1-2 sentences
- No emojis, keep professional exam style`;

    try {
        if (process.env.AI_SERVICES_ENABLED !== "false") {
            const topicLines = String(syllabusText || "")
                .split(/\r?\n/)
                .map((line) => line.replace(/^\s*[-*#\d.)]+\s*/, "").trim())
                .filter((line) => line.length >= 3 && line.length <= 120)
                .slice(0, 20);
            const targetNodeIds = (topicLines.length ? topicLines : ["General exam concepts"])
                .map((topic, index) => `GENERAL.${String(index + 1).padStart(3, "0")}`);
            const generated = await generateMock({
                mode: "exam_replica",
                questionCount: numQuestions,
                timeLimitMinutes: Math.max(1, numQuestions * 2),
                targetNodeIds
            });
            return (generated.questions || []).map((question) => ({
                question: question.question_text,
                options: question.options,
                answer: String.fromCharCode(65 + question.correct_option_index),
                explanation: question.explanation
            }));
        }
        const groq = getGroq();
        const completion = await groq.chat.completions.create({
            model: MODEL,
            messages: [{ role: "user", content: prompt }],
            temperature: 0.8,
            max_tokens: 2500,
            response_format: { type: "json_object" }
        });
        const text = completion.choices[0]?.message?.content || "[]";
        // Groq json_object wraps in an object sometimes
        const parsed = JSON.parse(text);
        if (Array.isArray(parsed)) return parsed;
        // handle {questions: [...]} wrapper
        return parsed.questions || parsed.mcqs || parsed.items || fallbackQuestions();
    } catch (error) {
        console.error("Error in generateMockExamQuestions:", error.message);
        return fallbackQuestions();
    }
};

function fallbackQuestions() {
    return [
        {
            question: "In operating systems, which scheduling algorithm gives minimum average waiting time for a given set of processes?",
            options: ["A) FCFS (First Come First Served)", "B) SJF (Shortest Job First)", "C) Round Robin", "D) Priority Scheduling"],
            answer: "B",
            explanation: "Shortest Job First (SJF) is provably optimal for minimizing average waiting time — it always picks the shortest available burst time next."
        },
        {
            question: "What is the time complexity of binary search on a sorted array of n elements?",
            options: ["A) O(n)", "B) O(n²)", "C) O(log n)", "D) O(1)"],
            answer: "C",
            explanation: "Binary search halves the search space at each step, giving O(log n) time complexity on a sorted array."
        },
        {
            question: "Which of the four Banker's Algorithm matrices determines how much more of each resource a process may still request?",
            options: ["A) Allocation matrix", "B) Available vector", "C) Max matrix", "D) Need matrix (Max - Allocation)"],
            answer: "D",
            explanation: "Need = Max - Allocation. It tells the system the maximum additional resources a process might need to complete execution."
        },
        {
            question: "In a page replacement algorithm, Belady's Anomaly occurs when:",
            options: ["A) LRU performs worse than FIFO", "B) Increasing page frames causes more page faults in FIFO", "C) Optimal replacement fails", "D) Thrashing increases CPU utilisation"],
            answer: "B",
            explanation: "Belady's Anomaly is specific to FIFO: adding more page frames can paradoxically increase the number of page faults — a counterintuitive behavior."
        },
        {
            question: "Which data structure provides O(1) average-case time for both insert and search operations?",
            options: ["A) Linked List", "B) Binary Search Tree", "C) Hash Table", "D) AVL Tree"],
            answer: "C",
            explanation: "Hash tables use a hash function to directly compute storage locations, achieving O(1) average case for insert, delete, and search (O(n) worst case with collisions)."
        }
    ];
}

/**
 * Chat QA compatibility facade. Primary calls go through ai_services.
 */
export const getGeminiChatStream = async (syllabusText, chatHistory, userMessage, userId = "guest", examId = undefined) => {
    if (process.env.AI_SERVICES_ENABLED !== "false") {
        const answer = await generateChatAnswer(userId, userMessage, undefined, examId);
        return (async function* () {
            yield { choices: [{ delta: { content: answer } }] };
        })();
    }
    const groq = getGroq();

    const systemPrompt = `You are a professional academic study tutor helping a student prepare for an exam.

Relevant syllabus and notes:
"""
${syllabusText ? syllabusText.substring(0, 4000) : "No specific syllabus. Answer general academic questions."}
"""

Guidelines:
1. Give academically rigorous, clear, and structured answers.
2. Use Markdown: headers, bullet points, numbered lists, code blocks where needed.
3. Relate all answers to exam preparation — highlight what's important.
4. Never use emojis or casual filler language.
5. If the concept involves a formula or algorithm, write it out explicitly.`;

    const messages = [
        { role: "system", content: systemPrompt },
        ...chatHistory.slice(-10).map(ch => ({
            role: ch.sender === "user" ? "user" : "assistant",
            content: ch.message
        })),
        { role: "user", content: userMessage }
    ];

    // Return a streaming completion — Groq streams natively via async iteration
    const stream = await groq.chat.completions.create({
        model: MODEL,
        messages,
        temperature: 0.6,
        max_tokens: 1500,
        stream: true
    });

    return stream;
};
