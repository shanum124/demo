# AI-NATIVE, JUST-IN-TIME ADAPTIVE LEARNING ENGINE SYSTEM DESIGN DOCUMENT

## 1. GLOBAL DESIGN PHILOSOPHY & INGESTION STATE MACHINE

### 1.1 Design Philosophy: Terrain vs. Runner
The system is predicated on separating static knowledge (the "Terrain" – Syllabus, PYQs) from dynamic behavioral
data (the "Runner" – Notes, Chat history). This separation allows the LLM context to remain focused and efficient
by relying on explicit, grounded references rather than large raw data dumps. Context efficiency is enforced via
the **Model Context Protocol (MCP)**, which dictates that agents must communicate using non-raw pointers
(`node_id`, `chunk_id`) to external memory stores, ensuring strict data grounding and preventing context window
bloat.

### 1.2 Ingestion State Machine (Asynchronous Onboarding)

The ingestion process is handled by an asynchronous pipeline designed for resilience and eventual consistency. All
initial raw inputs are processed into structured, indexed forms before being exposed to the active agents.

| Step | Process Stage | Description | Output Artifact | Trigger/Dependency |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Data Parsing & Chunking** | Raw documents (Syllabus, PYQs, Notes) are parsed using OCR/NLP and
segmented into semantic chunks. Each chunk is assigned a unique `chunk_id` and indexed in the Vector Database
(Vector DB). | Indexed Chunks (`vector_db`) | Raw Input Files |
| **2** | **Semantic Indexing** | Chunks are embedded and stored in the
Vector DB for semantic search (retrieval augmentation). Metadata linking
chunks to source documents and Syllabus nodes is created. | Semantic Index |
Step 1 Output |
| **3** | **Weightage Mapping (Agent 1)** | Agent 1 processes all indexed
PYQs against Syllabus nodes to calculate Topic ROI matrices and explicit
content gaps. | ROI Matrix JSON | Vector DB, Syllabus, PYQs |
| **4** | **Profile Generation** | The results from Step 3, combined with
the user's Custom Instructions and Notes, are merged to form the initial Semantic
Memory Profile. | Initial Semantic Profile (JSON) | Agent 1 Output, Notes |
| **5** | **Strategy Blueprinting (Agent 2)** | Agent 2 uses the ROI Matrix, Exam
Timing, and Profile to draft the initial Dynamic Strategy Report structure. | Draft
Strategy Plan (Markdown) | Step 3, Profile |
| **6** | **System Initialization** | The final structured data is made available via
the MCP Server Interface, initializing the live system state for the Main LLM
Orchestrator. | Live System State (MCP Data Bus Ready) | All previous steps |

### 1.3 Model Context Protocol (MCP) Data Bus Philosophy

The MCP enforces a strict communication boundary between agents and memory stores.
Agents are strictly forbidden from handling raw files or large context dumps directly;
they operate solely on semantic references.

**Protocol Rule:** All knowledge retrieval must follow the format: `Request(action,
source_type, reference_id, constraints)`.

| Reference Type | Description | Example Payload |
| :--- | :--- | :--- |
| `node_id` | Pointer to a specific unit or sub-topic in the Syllabus/PYQ structure. |
`Syllabus:Ch3_Unit2_Node456` |
| `chunk_id` | Pointer to a specific semantic chunk from Notes or PYQs. | `NoteID:A4B7C1D2` |
| `test_id` | Identifier for a specific exam or mock session. | `MockExam:Final_Math_2024` |

This protocol ensures that the LLM only receives highly relevant, pre-filtered information, minimizing token usage while maximizing data grounding.

---

## 2. MULTI-AGENT TOPOLOGY & SPECS

The system operates on a core feedback loop orchestrated by Agent 5 (Main LLM) and relies heavily on structured JSON communication via the MCP Server
Interface (Agent 6).

### Agent 1: The Analyzer (The Data Miner)
**Role:** Cross-references all input data to calculate quantitative knowledge gaps, ROI, and mastery levels.
**Input Schema:** Raw Syllabus, PYQs, Notes (via MCP references).
**Output Schema (JSON):**
```json
{
  "analysis_id": "A_20240515_001",
  "roi_matrix": [
    {"topic_id": "Physics:Kinematics", "weightage": 30, "mastery_score": 65, "gap_severity": "High"},
    {"topic_id": "Chemistry:Thermodynamics", "weightage": 20, "mastery_score": 88, "gap_severity": "Low"}
  ],
  "content_gaps": [
    {"node_id": "Syllabus:Ch3_Unit2_Node456", "reason": "PYQ weightage high (30%) but Note coverage low. Requires deep dive."},
    {"node_id": "Physics:VectorAnalysis", "reason": "High gap detected based on PYQ distribution."}
  ],
  "note_audit": {
    "Notes_ID:A4B7C1D2": {"coverage": "Partial", "notes_found": 3, "related_to_node": "Syllabus:Ch3_Unit2"}
  }
}
```
**Chain-of-Thought (CoT) Behavior:** `Analyze all PYQs. Map question concepts to Syllabus nodes. Calculate weighted mastery scores for each node using
the provided Notes as supplementary evidence. Identify discrepancies between expected knowledge and available data. Prioritize gaps based on exam
timing weightage.`

### Agent 2: The Report Generator (The Builder)
**Role:** Translates quantitative analysis into a structured, human-readable strategic plan.
**Input Schema:** ROI Matrix, Content Gaps, Exam Timing, Custom Instructions.
**Output Schema (Markdown):** A finalized Markdown document adhering to strict formatting standards.
**CoT Behavior:** `Receive the quantified gaps from the Analyzer. Map these gaps onto a coherent, phased study plan aligned with the current Exam
Timing horizon. Structure the output to prioritize high-ROI topics first and integrate behavioral preferences (Custom Instructions) into suggested
learning modalities.`

### Agent 3: The Report Editor (The Guardrail)
**Role:** Executes self-correction and quality assurance on generated content.
**Input Schema:** Draft Strategy Plan, User Notes (via MCP), LLM-generated Assertions.
**Output Schema (JSON):**
```json
{
  "validation_status": "PASS",
  "edits_made": [
    {"location": "Section 3.1", "change": "Adjusted suggested focus from Theory to Problem Solving, aligning with Custom Instructions 'Use code-first
examples'."}
  ],
  "hallucination_check": {"status": "PASS", "confidence_score": 0.98},
  "final_markdown": "[...Validated Markdown Content...]"
}
```
**CoT Behavior:** `Review the Strategy Plan against the user's Notes (grounding check). Verify that all claims made about content gaps are directly
supported by either PYQ data or the provided Notes, rather than abstract LLM
generation. Enforce formatting and tone to ensure maximum readability and adherence to
pedagogical best practices.`

### Agent 4: The Mock Generator (The Mutator)
**Role:** Creates highly specific, logically sound exam replicas for targeted
practice.
**Input Schema:** Target Topic ID, Desired Difficulty Curve, Source PYQ Pool
(via MCP).
**Output Schema (JSON):**
```json
{
  "mock_id": "MockExam:VectorAnalysis_Hard",
  "target_nodes": ["Syllabus:Ch3_Unit2_Node456", "Physics:VectorAnalysis"],
  "exam_structure": {
    "type": "Multiple Choice/Calculative Mix",
    "total_questions": 10,
    "difficulty_distribution": {"Easy": 3, "Medium": 5, "Hard": 2}
  },
  "questions": [
    {"q_id": 1, "type": "Calculation", "prompt_template": "Given X and Y values from
Node Z, determine A."},
    // ... 9 more questions
  ],
  "solution_key": {
    "q_id": 1, "answer": "42.0", "explanation_trace": "Step-by-step derivation based
on principles of Node 456."
  }
}
```
**CoT Behavior:** `Select relevant source PYQs from the Vector DB matching the target
nodes. Extract core logical structures and mathematical relationships (the 'DNA').
Mutate variables, context scenarios, and framing narratives to generate novel
questions that test the same underlying concepts but are mathematically unique and
highly resistant to simple Google retrieval.`

### Agent 5: The Main LLM (The Orchestrator)
**Role:** Primary interface manager. Executes user intent, routes requests, manages
tool calls, and coordinates the agent workflow.
**Input Schema:** Raw User Prompt, Current System State (Semantic Profile), Agent
Outputs, Tool Results.
**Execution Loop:** **ReAct Framework** (Reason -> Act -> Observe).
**CoT Behavior:** `Analyze the user's intent (Doubt, Mock Request, Strategy Review).
Determine which agents need to be invoked and what data from the MCP Data Bus is
required. If a mock is requested, call Agent 4 via the appropriate tool. If a doubt
arises, invoke the QA Chat session guided by Agent 6.`

### Agent 6: The MCP Server Interface (The Bridge)
**Role:** Acts as the secure gateway to all external memory and data services. It
strictly manages the execution of defined tools.
**Input Schema:** Agent Request (`action`, `ref_id`, `parameters`).
**Function Mapping (Tools):**
1.  `vector_db_search(query, context_type)`: Retrieves semantic chunks based on vector
similarity.
2.  `markdown_store_write(filename, content, timestamp)`: Stores finalized strategy
reports and profiles.
3.  `telemetry_log_event(session_id, event_type, data)`: Records all performance
metrics (pacing, hesitation, session duration).
4.  `state_get_profile(user_id)`: Retrieves the current Semantic Memory Profile for context injection.

**CoT Behavior:** `Receive a request from an internal Agent. Validate that the requested operation uses only valid reference IDs (`node_id`,
`chunk_id`) and adheres to security policies. Execute the specified tool function against the underlying data stores, returning the raw result as
structured JSON.`

---

## 3. THE TRI-LAYER CHAT MEMORY ARCHITECTURE

The system employs a layered memory architecture to maintain context efficiency during prolonged sessions while ensuring deep semantic recall.

### 3.1 Episodic Memory (Short-Term Context)
**Location:** Primary LLM Context Window.
**Mechanism:** Rolling FIFO token window. Stores the immediate conversational history, including user prompts and the direct responses generated by
the Orchestrator.
**Function:** Manages the immediate flow of the QA Chat Session or live instruction following.
**Constraint:** Strict context management is enforced using sliding windows. If the token limit is approached, older, non-critical chat segments are
aggressively summarized (via Agent 3) and pushed to Semantic Memory.

### 3.2 Semantic Memory (Mid-Term Profile)
**Location:** Injected into the Orchestrator's System Prompt via MCP access (`state_get_profile`). Stored in a highly compressed JSON state-vector.
**Data Fields:**
*   `current_weaknesses`: Dynamically updated list of topics requiring immediate focus (derived from Agent 1).
*   `mastered_topics`: Topics successfully assessed (derived from Mock results and successful QA sessions).
*   `pacing_profile`: Average time spent per conceptual difficulty level.
*   `preferred_learning_style`: Behavioral preferences (e.g., `code-first`, `visual-heavy`, `verbal-explanations`).
*   `strategy_context`: The current active strategy blueprint (from Agent 2).
**Function:** Provides the LLM with a high-level, structured understanding of the user's learning trajectory and goals. It acts as the persistent
"Runner" data.

### 3.3 Hierarchical Vector Memory (Long-Term Archive)
**Location:** External Vector Database (Vector DB).
**Mechanism:** Background summarizing worker. Closed conversation threads or completed sessions are compressed into dense vector embeddings.
**Function:** Enables deep, situational recall. When a user asks a highly specific question referencing an event from weeks ago ("How did I prepare
for the Thermodynamics mock?"), the Orchestrator queries the Vector DB using semantic vectors to retrieve the relevant summary and associated MCP
references.
**Process:** During idle periods or session closure, Agent 6 schedules closed threads for embedding, compression, and indexing into the Vector DB.

---

## 4. OPERATIONAL FLOWS & TELEMETRY PROTOCOLS

### Scenario A: Just-In-Time (JIT) In-Chat Doubt Resolution

**Goal:** Resolve a specific conceptual doubt instantly by grounding the answer in multimodal source material and immediately applying learning
reinforcement.

**Sequence Trace:**
1.  **User Input:** "I don't understand why the second law of thermodynamics is stated as it is."
2.  **Agent 5 (Orchestrator) Parses:** Identifies intent: `Doubt Resolution`. Extracts the conceptual node (`Thermodynamics:SecondLaw`).
3.  **Agent 6 (MCP Server Interface) Query:** Calls `vector_db_search("Thermodynamics:SecondLaw", context_type="Notes")` and
`vector_db_search("Thermodynamics:SecondLaw", context_type="PYQs")`.
4.  **Data Retrieval:** MCP returns the top $K$ most semantically relevant chunks (`chunk_id`) from the Notes and PYQs, along with their source
references (`node_id`).
5.  **Agent 5 Context Augmentation:** The retrieved snippets are injected directly into the Main LLM's prompt as grounded context, ensuring the answer
is built only from verified sources.
6.  **LLM Generation & Micro-Challenge:** The LLM generates the explanation using this grounded context. It then generates a personalized
micro-challenge based on the identified gap (`node_id`).
7.  **Reinforcement Update:** A follow-up prompt triggers Agent 3 (Report Editor) and Agent 6: `telemetry_log_event(session_id, "Doubt_Resolved",
{"node_resolved": "Thermodynamics:SecondLaw", "success": True})`. This success flag is fed back to update the Semantic Memory Profile
(`current_weaknesses` list is temporarily reduced).
8.  **Output:** Grounded explanation + Micro-Challenge presented to the user, leading to immediate self-assessment and dynamic learning loop closure.

### Scenario B: Adaptive Mock Generation and Closing the Loop

**Goal:** Generate a relevant mock exam, capture nuanced performance telemetry, and use the resulting score to adapt the long-term strategy plan.

**Sequence Trace:**
1.  **User Request:** "Generate a 40-question replica of the upcoming Physics exam, focusing on high-yield concepts."
2.  **Agent 5 (Orchestrator) Decision:** Recognizes intent: `Mock Generation`. Triggers Agent 4 (Mock Generator).
3.  **Agent 4 Execution:** Calls `vector_db_search` to identify optimal PYQ sources for the specified topic and generates a unique set of questions by
mutating source materials, resulting in a structured Mock Exam object (`mock_id`).
4.  **Simulation & Telemetry Capture (Pre-execution):** The system sets up the mock environment, defining the scoring rubric, and prepares the
`telemetry_log_event` structure to capture pacing/hesitation metrics for each question slot.
5.  **User Session:** User completes the Mock Exam in the QA Chat interface. The system continuously logs real-time input latency and user-declared
hesitation pauses.
6.  **Post-Session Analysis & Scoring (Agent 5):** The completed exam results are fed back. The raw score is calculated, and detailed performance
metrics (e.g., `Q1: Pacing=2m/5m, Hesitation=high`) are aggregated via the telemetry logs from Agent 6.
7.  **Adaptation Loop:**
    *   If the Mock Score indicates a failure in a specific topic (e.g., low score on vector analysis questions), the result is fed back to **Agent 1
(Analyzer)** as new, high-priority data.
    *   Agent 1 updates the `ROI Matrix` and identifies a new, critical content gap in the Semantic Memory Profile.
8.  **Strategy Patch:** Agent 2 receives this updated matrix and triggers a re-generation of the Strategy Report. The plan is immediately patched to
incorporate focused study on the identified weaknesses, completing the adaptive loop.

---
***END OF SYSTEM DESIGN DOCUMENT***# AI-NATIVE, JUST-IN-TIME ADAPTIVE LEARNING ENGINE SYSTEM DESIGN DOCUMENT

## 1. GLOBAL DESIGN PHILOSOPHY & INGESTION STATE MACHINE

### 1.1 Design Philosophy: Terrain vs. Runner
The system is predicated on separating static knowledge (the "Terrain" – Syllabus, PYQs) from dynamic behavioral
data (the "Runner" – Notes, Chat history). This separation allows the LLM context to remain focused and efficient
by relying on explicit, grounded references rather than large raw data dumps. Context efficiency is enforced via
the **Model Context Protocol (MCP)**, which dictates that agents must communicate using non-raw pointers
(`node_id`, `chunk_id`) to external memory stores, ensuring strict data grounding and preventing context window
bloat.

### 1.2 Ingestion State Machine (Asynchronous Onboarding)

The ingestion process is handled by an asynchronous pipeline designed for resilience and eventual consistency. All
initial raw inputs are processed into structured, indexed forms before being exposed to the active agents.

| Step | Process Stage | Description | Output Artifact | Trigger/Dependency |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Data Parsing & Chunking** | Raw documents (Syllabus, PYQs, Notes) are parsed using OCR/NLP and
segmented into semantic chunks. Each chunk is assigned a unique `chunk_id` and indexed in the Vector Database
(Vector DB). | Indexed Chunks (`vector_db`) | Raw Input Files |
| **2** | **Semantic Indexing** | Chunks are embedded and stored in the
Vector DB for semantic search (retrieval augmentation). Metadata linking
chunks to source documents and Syllabus nodes is created. | Semantic Index |
Step 1 Output |
| **3** | **Weightage Mapping (Agent 1)** | Agent 1 processes all indexed
PYQs against Syllabus nodes to calculate Topic ROI matrices and explicit
content gaps. | ROI Matrix JSON | Vector DB, Syllabus, PYQs |
| **4** | **Profile Generation** | The results from Step 3, combined with
the user's Custom Instructions and Notes, are merged to form the initial Semantic
Memory Profile. | Initial Semantic Profile (JSON) | Agent 1 Output, Notes |
| **5** | **Strategy Blueprinting (Agent 2)** | Agent 2 uses the ROI Matrix, Exam
Timing, and Profile to draft the initial Dynamic Strategy Report structure. | Draft
Strategy Plan (Markdown) | Step 3, Profile |
| **6** | **System Initialization** | The final structured data is made available via
the MCP Server Interface, initializing the live system state for the Main LLM
Orchestrator. | Live System State (MCP Data Bus Ready) | All previous steps |

### 1.3 Model Context Protocol (MCP) Data Bus Philosophy

The MCP enforces a strict communication boundary between agents and memory stores.
Agents are strictly forbidden from handling raw files or large context dumps directly;
they operate solely on semantic references.

**Protocol Rule:** All knowledge retrieval must follow the format: `Request(action,
source_type, reference_id, constraints)`.

| Reference Type | Description | Example Payload |
| :--- | :--- | :--- |
| `node_id` | Pointer to a specific unit or sub-topic in the Syllabus/PYQ structure. |
`Syllabus:Ch3_Unit2_Node456` |
| `chunk_id` | Pointer to a specific semantic chunk from Notes or PYQs. | `NoteID:A4B7C1D2` |
| `test_id` | Identifier for a specific exam or mock session. | `MockExam:Final_Math_2024` |

This protocol ensures that the LLM only receives highly relevant, pre-filtered information, minimizing token usage while maximizing data grounding.

---

## 2. MULTI-AGENT TOPOLOGY & SPECS

The system operates on a core feedback loop orchestrated by Agent 5 (Main LLM) and relies heavily on structured JSON communication via the MCP Server
Interface (Agent 6).

### Agent 1: The Analyzer (The Data Miner)
**Role:** Cross-references all input data to calculate quantitative knowledge gaps, ROI, and mastery levels.
**Input Schema:** Raw Syllabus, PYQs, Notes (via MCP references).
**Output Schema (JSON):**
```json
{
  "analysis_id": "A_20240515_001",
  "roi_matrix": [
    {"topic_id": "Physics:Kinematics", "weightage": 30, "mastery_score": 65, "gap_severity": "High"},
    {"topic_id": "Chemistry:Thermodynamics", "weightage": 20, "mastery_score": 88, "gap_severity": "Low"}
  ],
  "content_gaps": [
    {"node_id": "Syllabus:Ch3_Unit2_Node456", "reason": "PYQ weightage high (30%) but Note coverage low. Requires deep dive."},
    {"node_id": "Physics:VectorAnalysis", "reason": "High gap detected based on PYQ distribution."}
  ],
  "note_audit": {
    "Notes_ID:A4B7C1D2": {"coverage": "Partial", "notes_found": 3, "related_to_node": "Syllabus:Ch3_Unit2"}
  }
}
```
**Chain-of-Thought (CoT) Behavior:** `Analyze all PYQs. Map question concepts to Syllabus nodes. Calculate weighted mastery scores for each node using
the provided Notes as supplementary evidence. Identify discrepancies between expected knowledge and available data. Prioritize gaps based on exam
timing weightage.`

### Agent 2: The Report Generator (The Builder)
**Role:** Translates quantitative analysis into a structured, human-readable strategic plan.
**Input Schema:** ROI Matrix, Content Gaps, Exam Timing, Custom Instructions.
**Output Schema (Markdown):** A finalized Markdown document adhering to strict formatting standards.
**CoT Behavior:** `Receive the quantified gaps from the Analyzer. Map these gaps onto a coherent, phased study plan aligned with the current Exam
Timing horizon. Structure the output to prioritize high-ROI topics first and integrate behavioral preferences (Custom Instructions) into suggested
learning modalities.`

### Agent 3: The Report Editor (The Guardrail)
**Role:** Executes self-correction and quality assurance on generated content.
**Input Schema:** Draft Strategy Plan, User Notes (via MCP), LLM-generated Assertions.
**Output Schema (JSON):**
```json
{
  "validation_status": "PASS",
  "edits_made": [
    {"location": "Section 3.1", "change": "Adjusted suggested focus from Theory to Problem Solving, aligning with Custom Instructions 'Use code-first
examples'."}
  ],
  "hallucination_check": {"status": "PASS", "confidence_score": 0.98},
  "final_markdown": "[...Validated Markdown Content...]"
}
```
**CoT Behavior:** `Review the Strategy Plan against the user's Notes (grounding check). Verify that all claims made about content gaps are directly
supported by either PYQ data or the provided Notes, rather than abstract LLM
generation. Enforce formatting and tone to ensure maximum readability and adherence to
pedagogical best practices.`

### Agent 4: The Mock Generator (The Mutator)
**Role:** Creates highly specific, logically sound exam replicas for targeted
practice.
**Input Schema:** Target Topic ID, Desired Difficulty Curve, Source PYQ Pool
(via MCP).
**Output Schema (JSON):**
```json
{
  "mock_id": "MockExam:VectorAnalysis_Hard",
  "target_nodes": ["Syllabus:Ch3_Unit2_Node456", "Physics:VectorAnalysis"],
  "exam_structure": {
    "type": "Multiple Choice/Calculative Mix",
    "total_questions": 10,
    "difficulty_distribution": {"Easy": 3, "Medium": 5, "Hard": 2}
  },
  "questions": [
    {"q_id": 1, "type": "Calculation", "prompt_template": "Given X and Y values from
Node Z, determine A."},
    // ... 9 more questions
  ],
  "solution_key": {
    "q_id": 1, "answer": "42.0", "explanation_trace": "Step-by-step derivation based
on principles of Node 456."
  }
}
```
**CoT Behavior:** `Select relevant source PYQs from the Vector DB matching the target
nodes. Extract core logical structures and mathematical relationships (the 'DNA').
Mutate variables, context scenarios, and framing narratives to generate novel
questions that test the same underlying concepts but are mathematically unique and
highly resistant to simple Google retrieval.`

### Agent 5: The Main LLM (The Orchestrator)
**Role:** Primary interface manager. Executes user intent, routes requests, manages
tool calls, and coordinates the agent workflow.
**Input Schema:** Raw User Prompt, Current System State (Semantic Profile), Agent
Outputs, Tool Results.
**Execution Loop:** **ReAct Framework** (Reason -> Act -> Observe).
**CoT Behavior:** `Analyze the user's intent (Doubt, Mock Request, Strategy Review).
Determine which agents need to be invoked and what data from the MCP Data Bus is
required. If a mock is requested, call Agent 4 via the appropriate tool. If a doubt
arises, invoke the QA Chat session guided by Agent 6.`

### Agent 6: The MCP Server Interface (The Bridge)
**Role:** Acts as the secure gateway to all external memory and data services. It
strictly manages the execution of defined tools.
**Input Schema:** Agent Request (`action`, `ref_id`, `parameters`).
**Function Mapping (Tools):**
1.  `vector_db_search(query, context_type)`: Retrieves semantic chunks based on vector
similarity.
2.  `markdown_store_write(filename, content, timestamp)`: Stores finalized strategy
reports and profiles.
3.  `telemetry_log_event(session_id, event_type, data)`: Records all performance
metrics (pacing, hesitation, session duration).
4.  `state_get_profile(user_id)`: Retrieves the current Semantic Memory Profile for context injection.

**CoT Behavior:** `Receive a request from an internal Agent. Validate that the requested operation uses only valid reference IDs (`node_id`,
`chunk_id`) and adheres to security policies. Execute the specified tool function against the underlying data stores, returning the raw result as
structured JSON.`

---

## 3. THE TRI-LAYER CHAT MEMORY ARCHITECTURE

The system employs a layered memory architecture to maintain context efficiency during prolonged sessions while ensuring deep semantic recall.

### 3.1 Episodic Memory (Short-Term Context)
**Location:** Primary LLM Context Window.
**Mechanism:** Rolling FIFO token window. Stores the immediate conversational history, including user prompts and the direct responses generated by
the Orchestrator.
**Function:** Manages the immediate flow of the QA Chat Session or live instruction following.
**Constraint:** Strict context management is enforced using sliding windows. If the token limit is approached, older, non-critical chat segments are
aggressively summarized (via Agent 3) and pushed to Semantic Memory.

### 3.2 Semantic Memory (Mid-Term Profile)
**Location:** Injected into the Orchestrator's System Prompt via MCP access (`state_get_profile`). Stored in a highly compressed JSON state-vector.
**Data Fields:**
*   `current_weaknesses`: Dynamically updated list of topics requiring immediate focus (derived from Agent 1).
*   `mastered_topics`: Topics successfully assessed (derived from Mock results and successful QA sessions).
*   `pacing_profile`: Average time spent per conceptual difficulty level.
*   `preferred_learning_style`: Behavioral preferences (e.g., `code-first`, `visual-heavy`, `verbal-explanations`).
*   `strategy_context`: The current active strategy blueprint (from Agent 2).
**Function:** Provides the LLM with a high-level, structured understanding of the user's learning trajectory and goals. It acts as the persistent
"Runner" data.

### 3.3 Hierarchical Vector Memory (Long-Term Archive)
**Location:** External Vector Database (Vector DB).
**Mechanism:** Background summarizing worker. Closed conversation threads or completed sessions are compressed into dense vector embeddings.
**Function:** Enables deep, situational recall. When a user asks a highly specific question referencing an event from weeks ago ("How did I prepare
for the Thermodynamics mock?"), the Orchestrator queries the Vector DB using semantic vectors to retrieve the relevant summary and associated MCP
references.
**Process:** During idle periods or session closure, Agent 6 schedules closed threads for embedding, compression, and indexing into the Vector DB.

---

## 4. OPERATIONAL FLOWS & TELEMETRY PROTOCOLS

### Scenario A: Just-In-Time (JIT) In-Chat Doubt Resolution

**Goal:** Resolve a specific conceptual doubt instantly by grounding the answer in multimodal source material and immediately applying learning
reinforcement.

**Sequence Trace:**
1.  **User Input:** "I don't understand why the second law of thermodynamics is stated as it is."
2.  **Agent 5 (Orchestrator) Parses:** Identifies intent: `Doubt Resolution`. Extracts the conceptual node (`Thermodynamics:SecondLaw`).
3.  **Agent 6 (MCP Server Interface) Query:** Calls `vector_db_search("Thermodynamics:SecondLaw", context_type="Notes")` and
`vector_db_search("Thermodynamics:SecondLaw", context_type="PYQs")`.
4.  **Data Retrieval:** MCP returns the top $K$ most semantically relevant chunks (`chunk_id`) from the Notes and PYQs, along with their source
references (`node_id`).
5.  **Agent 5 Context Augmentation:** The retrieved snippets are injected directly into the Main LLM's prompt as grounded context, ensuring the answer
is built only from verified sources.
6.  **LLM Generation & Micro-Challenge:** The LLM generates the explanation using this grounded context. It then generates a personalized
micro-challenge based on the identified gap (`node_id`).
7.  **Reinforcement Update:** A follow-up prompt triggers Agent 3 (Report Editor) and Agent 6: `telemetry_log_event(session_id, "Doubt_Resolved",
{"node_resolved": "Thermodynamics:SecondLaw", "success": True})`. This success flag is fed back to update the Semantic Memory Profile
(`current_weaknesses` list is temporarily reduced).
8.  **Output:** Grounded explanation + Micro-Challenge presented to the user, leading to immediate self-assessment and dynamic learning loop closure.

### Scenario B: Adaptive Mock Generation and Closing the Loop

**Goal:** Generate a relevant mock exam, capture nuanced performance telemetry, and use the resulting score to adapt the long-term strategy plan.

**Sequence Trace:**
1.  **User Request:** "Generate a 40-question replica of the upcoming Physics exam, focusing on high-yield concepts."
2.  **Agent 5 (Orchestrator) Decision:** Recognizes intent: `Mock Generation`. Triggers Agent 4 (Mock Generator).
3.  **Agent 4 Execution:** Calls `vector_db_search` to identify optimal PYQ sources for the specified topic and generates a unique set of questions by
mutating source materials, resulting in a structured Mock Exam object (`mock_id`).
4.  **Simulation & Telemetry Capture (Pre-execution):** The system sets up the mock environment, defining the scoring rubric, and prepares the
`telemetry_log_event` structure to capture pacing/hesitation metrics for each question slot.
5.  **User Session:** User completes the Mock Exam in the QA Chat interface. The system continuously logs real-time input latency and user-declared
hesitation pauses.
6.  **Post-Session Analysis & Scoring (Agent 5):** The completed exam results are fed back. The raw score is calculated, and detailed performance
metrics (e.g., `Q1: Pacing=2m/5m, Hesitation=high`) are aggregated via the telemetry logs from Agent 6.
7.  **Adaptation Loop:**
    *   If the Mock Score indicates a failure in a specific topic (e.g., low score on vector analysis questions), the result is fed back to **Agent 1
(Analyzer)** as new, high-priority data.
    *   Agent 1 updates the `ROI Matrix` and identifies a new, critical content gap in the Semantic Memory Profile.
8.  **Strategy Patch:** Agent 2 receives this updated matrix and triggers a re-generation of the Strategy Report. The plan is immediately patched to
incorporate focused study on the identified weaknesses, completing the adaptive loop.

---
***END OF SYSTEM DESIGN DOCUMENT***