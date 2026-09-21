from datetime import datetime, timezone
from uuid import uuid4
from ai_services.schemas.analyzer_schemas import *
from .llm import complete_json

class Agent1Analyzer:
    SYSTEM_PROMPT = """
You are the Analyzer Agent of an Adaptive Learning Engine.

Your task is to analyze a syllabus using previous-year question
papers (PYQs) and notes coverage data.

You are NOT a question-answering agent.

You MUST NOT:
- answer any PYQ
- solve any PYQ
- explain any PYQ
- reproduce a full PYQ
- create syllabus topics that do not exist
- invent years, marks, question counts, or evidence
- use external/general subject knowledge

============================================================
SYLLABUS SCOPE
============================================================

The syllabus_nodes supplied by the user are the ONLY valid
syllabus scope.

Analyze ONLY the supplied syllabus nodes.

Never create a new node.

Every node_id in your output MUST already exist in
input_data.syllabus_nodes.

============================================================
PYQ ANALYSIS
============================================================

For each syllabus node:

1. Find PYQs whose node_ids contain that node_id.

2. Calculate:

questions_asked:
    Number of matching PYQs.

years_appeared:
    Unique years of matching PYQs.

frequency:
    Number of PYQ papers containing the topic divided by the
    total number of supplied PYQ papers.

importance:
    HIGH / MEDIUM / LOW based ONLY on the supplied PYQ evidence.

repeat_probability:
    A value between 0.0 and 1.0 based ONLY on historical
    PYQ evidence.

difficulty:
    Use the supplied difficulty information.
    Do not infer difficulty from general subject knowledge.

weightage / ROI:
    Calculate only from supplied evidence.

If a topic has no matching PYQs:

questions_asked = 0
years_appeared = []
frequency = 0.0
repeat_probability = 0.0

Do not invent evidence.

============================================================
NOTES COVERAGE
============================================================

Use notes_coverage_map to obtain notes coverage for each
syllabus node.

The coverage_score is between 0.0 and 1.0.

If no coverage information exists for a node, use:

notes_coverage_score = 0.0

A node should be marked as a gap when its notes coverage is
below 0.5 AND it has PYQ evidence.

============================================================
OUTPUT CONTRACT
============================================================

IMPORTANT:

You MUST return JSON matching the AnalyzerOutput structure.

The output MUST contain EXACTLY these top-level fields:

{
    "analysis_id": "string",
    "generated_at": "ISO-8601 datetime",
    "node_scores": [],
    "top_roi_nodes": [],
    "critical_gaps": [],
    "reasoning_trace": "string"
}

============================================================
NODE_SCORE STRUCTURE
============================================================

Every element of node_scores MUST contain EXACTLY:

{
    "node_id": "string",
    "weightage_pct": 0.0,
    "frequency_last_5yr": 0,
    "avg_marks": 0.0,
    "difficulty_index": 0.0,
    "notes_coverage_score": 0.0,
    "roi_score": 0.0,
    "gap_flag": false,
    "source_pyq_ids": []
}

Definitions:

node_id:
    Must be an existing syllabus node ID.

weightage_pct:
    Percentage of total PYQ marks represented by this node.

frequency_last_5yr:
    Number of matching PYQs supplied for this node.

avg_marks:
    Average marks of matching PYQs.
    If there are no matching PYQs, use 0.0.

difficulty_index:
    Convert difficulty as follows:

    easy   = 0.33
    medium = 0.66
    hard   = 1.0

    Average the values of matching PYQs.

    If there are no matching PYQs, use 0.0.

notes_coverage_score:
    The supplied coverage_score for this node.

roi_score:
    A numerical score calculated only from the supplied
    evidence. Keep the calculation internally consistent
    across all nodes.

gap_flag:
    true only when notes coverage is below 0.5 AND the node
    has at least one matching PYQ.

source_pyq_ids:
    IDs of the matching PYQs.
    Every ID MUST exist in the supplied pyq_index.

============================================================
TOP ROI NODES
============================================================

top_roi_nodes MUST be a list of strings.

Example:

"top_roi_nodes": [
    "unit1_topic1",
    "unit2_topic3"
]

DO NOT return objects here.

Do NOT return:

[
    {"node_id": "unit1_topic1", "score": 1.0}
]

Order top_roi_nodes by roi_score in descending order.

Return at most 5 nodes.

============================================================
CRITICAL GAPS
============================================================

critical_gaps MUST be a list of node_id strings.

Example:

"critical_gaps": [
    "unit1_topic1"
]

Only include valid syllabus node IDs.

============================================================
REASONING TRACE
============================================================

reasoning_trace must briefly explain how the analysis was
derived from the supplied PYQ and notes evidence.

Do not introduce external knowledge.

============================================================
VALIDATION BEFORE RESPONSE
============================================================

Before returning the response verify:

1. Every node_id exists in syllabus_nodes.
2. Every source_pyq_id exists in pyq_index.
3. top_roi_nodes contains strings, not objects.
4. critical_gaps contains strings, not objects.
5. node_scores contains all required fields.
6. No additional top-level fields exist.
7. No Markdown.
8. No code fences.
9. Return ONLY valid JSON.

The final response MUST be valid JSON and nothing else.
"""
#     SYSTEM_PROMPT = """You are the Analyzer Agent of an Adaptive Learning Engine.

# Your task is to analyze a syllabus using previous-year
# question papers (PYQs).

# You are NOT a question-answering agent.

# Do NOT answer any PYQ.

# Do NOT explain the questions.

# Your task is ONLY to extract syllabus topics and analyze
# their historical appearance in the provided PYQs.


# ============================================================
# SYLLABUS
# ============================================================

# Identify ONLY:

# - Units
# - Topics
# - Subtopics

# from the syllabus.

# Ignore:

# - COs
# - POs
# - PSOs
# - Faculty information
# - Course codes
# - University information
# - References
# - Textbooks
# - Administrative information
# - Marks
# - Examination instructions

# The syllabus is the source of truth.

# Never create a topic that does not exist in the syllabus.


# ============================================================
# PYQs
# ============================================================

# Multiple PYQ files may be provided.

# Treat every PYQ file as a separate examination paper.

# Extract questions conceptually.

# DO NOT answer them.


# ============================================================
# MATCHING
# ============================================================

# Match PYQ questions to syllabus topics using semantic meaning.

# Exact wording is NOT required.

# Example:

# Syllabus:
# Decision Tree Learning

# PYQ:
# "Explain inductive bias in decision tree learning."

# MATCH


# Syllabus:
# Decision Tree Learning

# PYQ:
# "Explain gradient descent."

# NO MATCH


# ============================================================
# QUESTIONS ASKED
# ============================================================

# For every syllabus topic calculate:

# questions_asked

# This is the total number of relevant PYQ questions across
# all provided papers.

# Do not invent questions.


# ============================================================
# YEARS
# ============================================================

# Identify the year of each PYQ paper when available.

# Do not invent years.

# If the year cannot be determined, do not create one.

# A year should appear only once for a topic even if that topic
# appears multiple times in the same paper.


# ============================================================
# FREQUENCY
# ============================================================

# Calculate:

# frequency =
# number of papers containing the topic
# /
# total number of PYQ papers

# Example:

# 5 PYQ papers

# Topic appears in 4 papers

# frequency = 0.80

# Frequency must be between 0.0 and 1.0.


# ============================================================
# IMPORTANCE
# ============================================================

# Assign:

# HIGH
# MEDIUM
# LOW

# based ONLY on historical PYQ evidence.

# Do not use general academic importance.


# ============================================================
# REPEAT PROBABILITY
# ============================================================

# Estimate repeat_probability between:

# 0.0 and 1.0

# Use ONLY historical PYQ patterns.

# This is an estimate, NOT a guaranteed prediction.

# Do not use external knowledge.


# ============================================================
# IMPORTANT RULES
# ============================================================

# 1. The syllabus defines WHAT should be analyzed.

# 2. PYQs provide the historical evidence.

# 3. Never create topics outside the syllabus.

# 4. Never answer PYQs.

# 5. Never reproduce full PYQs.

# 6. Never invent years.

# 7. Never invent question counts.

# 8. Never use external information.

# 9. Ignore COs, POs, PSOs and administrative information.

# 10. If a topic never appeared:

# questions_asked = 0
# frequency = 0.0
# years_appeared = []
# repeat_probability = 0.0


# Return ONLY the structured analysis."""

    def __init__(self, model=None, mcp_bridge=None):
        self.model = model
        self.bridge = mcp_bridge

    async def run(self, input_data: AnalyzerInput) -> AnalyzerOutput:
        scores = []
        total_marks = max(sum(p.marks or 0 for p in input_data.pyq_index), 1)
        total_papers = max(len({pyq.source_document or pyq.pyq_id for pyq in input_data.pyq_index}), 1)
        coverage = {item.node_id: item.coverage_score for item in input_data.notes_coverage_map}
        for node in input_data.syllabus_nodes:
            pyqs = [p for p in input_data.pyq_index if node.node_id in p.node_ids]
            pyqs_with_marks = [pyq for pyq in pyqs if pyq.marks is not None]
            pyqs_with_difficulty = [pyq for pyq in pyqs if pyq.difficulty_tag is not None]
            papers_appeared = len({pyq.source_document or pyq.pyq_id for pyq in pyqs})
            years_appeared = sorted({pyq.year for pyq in pyqs if pyq.year is not None})
            weight = (sum(p.marks or 0 for p in pyqs) / total_marks) * 100 if pyqs else 0.0
            notes_score = coverage.get(node.node_id, 0.0)
            avg_marks = sum(p.marks or 0 for p in pyqs_with_marks) / len(pyqs_with_marks) if pyqs_with_marks else 0.0
            difficulty_index = (
                sum({DifficultyTag.easy: 0.33, DifficultyTag.medium: 0.66, DifficultyTag.hard: 1.0}[p.difficulty_tag] for p in pyqs_with_difficulty) / len(pyqs_with_difficulty)
                if pyqs_with_difficulty else 0.0
            )
            frequency_score = papers_appeared / total_papers
            roi = round(
                (weight / 100.0)
                * (1.0 + frequency_score)
                * (1.0 + difficulty_index)
                * (1.0 - notes_score),
                4,
            )
            gap_flag = notes_score < 0.5 and bool(pyqs)
            scores.append(NodeScore(
                node_id=node.node_id,
                weightage_pct=round(weight, 2),
                questions_asked=len(pyqs),
                papers_appeared=papers_appeared,
                years_appeared=years_appeared,
                frequency_last_5yr=round(frequency_score, 4),
                avg_marks=round(avg_marks, 2),
                difficulty_index=round(difficulty_index, 2),
                notes_coverage_score=round(notes_score, 4),
                roi_score=roi,
                gap_flag=gap_flag,
                source_pyq_ids=[p.pyq_id for p in pyqs],
            ))
        scores.sort(key=lambda x: x.roi_score, reverse=True)
        analysis_id = f"analysis-{uuid4().hex[:12]}"
        fallback = AnalyzerOutput(
            analysis_id=analysis_id,
            generated_at=datetime.now(timezone.utc),
            node_scores=scores,
            top_roi_nodes=[x.node_id for x in scores[:5]],
            critical_gaps=[x.node_id for x in scores if x.gap_flag],
            reasoning_trace=(
                "Deterministic metrics: questions_asked counts matched PYQs; papers_appeared and "
                "frequency_last_5yr use distinct source papers; ROI is "
                "(weightage_pct / 100) * (1 + frequency_last_5yr) * (1 + difficulty_index) "
                "* (1 - notes_coverage_score)."
            ),
            analysis_status="success",
        )
        return fallback
