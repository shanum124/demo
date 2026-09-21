import re
from datetime import datetime, timezone
from typing import TypedDict
try:
    from langgraph.graph import END, START, StateGraph
except ImportError:
    END = START = StateGraph = None
from ai_services.schemas.mcp_schemas import TelemetryEvent, VectorSearchRequest
from ai_services.schemas.orchestrator_schemas import *
from ai_services.schemas.mock_schemas import MockGeneratorInput, MockMode
from .agent4_mock_generator import MockGenerationError
from .llm import complete_json
class Agent5Orchestrator:
    SYSTEM_PROMPT = """You are Agent 5, the learning-session orchestrator.
Classify the learner's intent as chat_qa, doubt_solve, mock_request, or report_query.
Respond helpfully and concisely using the supplied profile and conversation only.
Use action.tool_call only when a tool is genuinely needed; never expose tool syntax.
Return exactly one JSON object matching OrchestratorOutput. No Markdown fences."""

    def __init__(self, model=None, mcp_bridge=None, episodic_memory=None, mock_generator=None):
        self.model = model
        self.bridge = mcp_bridge
        self.episodic = episodic_memory
        self.mock_gen = mock_generator

    def _build_graph(self):
        if StateGraph is None:
            return None
        orchestrator = self

        class State(TypedDict, total=False):
            request: OrchestratorInput
            output: OrchestratorOutput
            intent: str
            retrieved: str

        async def classify(state: State):
            request = state["request"]
            fallback_intent = "doubt_solve" if "why" in request.user_message.lower() or "doubt" in request.user_message.lower() else "mock_request" if "mock" in request.user_message.lower() or "quiz" in request.user_message.lower() else "report_query" if "report" in request.user_message.lower() or "study plan" in request.user_message.lower() else "chat_qa"
            output = OrchestratorOutput(intent_class=fallback_intent, assistant_response="I can help you work through that.", action=ActionBlock(spawn_thread=fallback_intent == "doubt_solve"))
            if orchestrator.model is not None:
                try:
                    result = await complete_json(orchestrator.model, orchestrator.SYSTEM_PROMPT, request.model_dump_json(), OrchestratorOutput)
                    output = OrchestratorOutput.model_validate(result)
                except Exception:
                    pass
            return {"output": output, "intent": output.intent_class}

        async def retrieve(state: State):
            request = state["request"]
            try:
                results = await orchestrator.bridge.vector_db_search(VectorSearchRequest(
                    query=request.user_message,
                    exam_id=request.exam_id,
                ))
            except Exception:
                # A retrieval dependency must not suppress the tutor's response.
                results = []
            return {"retrieved": "\n".join(result.snippet for result in results)}

        async def generate_mock(state: State):
            output = state["output"]
            return {"output": output.model_copy(update={"assistant_response": "Open the Assessment tab to generate a mock from the active exam's analyzer and PYQ evidence."})}

        async def respond(state: State):
            output = state["output"]
            if state.get("intent") == "chat_qa":
                evidence = state.get("retrieved", "")
                output = output.model_copy(update={"assistant_response": f"Here is a grounded starting point:\n\n{evidence or 'I need indexed notes or a more specific topic to ground this answer.'}"})
            return {"output": output}

        def route(state: State):
            return "mock" if state.get("intent") == "mock_request" else "retrieve" if state.get("intent") == "chat_qa" else "respond"

        graph = StateGraph(State)
        graph.add_node("classify", classify)
        graph.add_node("retrieve", retrieve)
        graph.add_node("mock", generate_mock)
        graph.add_node("respond", respond)
        graph.add_edge(START, "classify")
        graph.add_conditional_edges("classify", route, {"retrieve": "retrieve", "mock": "mock", "respond": "respond"})
        graph.add_edge("retrieve", "respond")
        graph.add_edge("mock", "respond")
        graph.add_edge("respond", END)
        return graph.compile()

    async def run(self, input_data: OrchestratorInput) -> OrchestratorOutput:
        graph = self._build_graph()
        if graph is None:
            text = input_data.user_message.lower()
            intent = "doubt_solve" if "why" in text or "doubt" in text else "mock_request" if "mock" in text or "quiz" in text else "report_query" if "report" in text or "study plan" in text else "chat_qa"
            output = OrchestratorOutput(intent_class=intent, assistant_response="I can help you work through that.", action=ActionBlock(spawn_thread=intent == "doubt_solve"))
            if intent == "chat_qa":
                try:
                    results = await self.bridge.vector_db_search(VectorSearchRequest(
                        query=input_data.user_message,
                        exam_id=input_data.exam_id,
                    ))
                except Exception:
                    results = []
                output = output.model_copy(update={"assistant_response": "Here is a grounded starting point:\n\n" + (results[0].snippet if results else "I need indexed notes or a more specific topic to ground this answer.")})
            elif intent == "mock_request":
                output = output.model_copy(update={"assistant_response": "Open the Assessment tab to generate a mock from the active exam's analyzer and PYQ evidence."})
        else:
            state = await graph.ainvoke({"request": input_data})
            output = state["output"]
        await self.bridge.telemetry_log_event(TelemetryEvent(event_type="chat_turn", payload={"intent": output.intent_class}, ts=datetime.now(timezone.utc), user_id=input_data.user_id))
        return output
