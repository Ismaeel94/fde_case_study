from langgraph.graph import StateGraph

from app.services.skills.customer_escalation_summary import CustomerEscalationGraph
from langchain_core.messages import BaseMessage
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from typing import Literal
from langgraph.graph import END
from langchain_core.messages import SystemMessage, HumanMessage
from functools import lru_cache
from pathlib import Path
from app.core.config import PROJECT_ROOT
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from app.services.skills.customer_escalation_summary import EscalationSummaryState


INTENT_PROMPT_PATH = (PROJECT_ROOT / "app" / "prompts" / "intent_prompt.txt")
GENERAL_AGENT_SYSTEM_PROMPT_PATH = (PROJECT_ROOT / "app" / "prompts" / "general_agent_system_prompt.txt")
CUSTOMER_NAME_EXTRACTION_PROMPT_PATH = (PROJECT_ROOT / "app" / "prompts" / "customer_name_extraction_prompt.txt")

@lru_cache
def _load_customer_name_extraction_prompt() -> str:
    return CUSTOMER_NAME_EXTRACTION_PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache
def _load_intent_prompt() -> str:
    return INTENT_PROMPT_PATH.read_text(encoding="utf-8")

@lru_cache
def _load_general_agent_system_prompt() -> str:
    return GENERAL_AGENT_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

class CustomerNameExtraction(BaseModel):
    customer_name: str | None
    confidence: Literal["low", "medium", "high"]
    reason: str

class IntentDecision(BaseModel):
    intent: Literal["customer_escalation_summary", "general_agent", "both", "none"]
    customer_name: str | None = None

class MasterGraphState(TypedDict):
    intent: Literal["customer_escalation_summary", "general_agent", "both", "none"]
    messages: Annotated[list[BaseMessage], add_messages]
    customer_name: str
    customer_name_confidence: Literal["low", "medium", "high"]
    customer_name_reason: str
    customer_escalation_summary: EscalationSummaryState
    general_agent_response: str
    response: str


class MasterGraph:
    def __init__(self, llm, tools):
        self.llm = llm
        self.tools = tools
        self.intent_llm = llm.with_structured_output(IntentDecision)
        self.general_react_agent = create_react_agent(model=llm, tools=tools, prompt=_load_general_agent_system_prompt())   
        self.customer_escalation_graph_object = CustomerEscalationGraph(llm=llm, tools=tools)
        self.customer_name_llm = llm.with_structured_output(CustomerNameExtraction)

        graph = StateGraph(MasterGraphState)
        graph.add_node("prepare_query", self.prepare_query)
        graph.add_node("extract_intent", self.extract_intent)
        graph.add_node("extract_customer_name", self.extract_customer_name)
        graph.add_node("extract_customer_name_for_both", self.extract_customer_name_for_both)
        graph.add_node("run_general_agent", self.run_general_agent)
        graph.add_node("run_customer_escalation_summary", self.run_customer_escalation_summary)
        graph.add_node("synthesise_response", self.synthesise_response)
        graph.add_node("none", self.none)
        
        graph.set_entry_point("prepare_query")
        graph.add_conditional_edges(
            "extract_customer_name",
            self.handle_customer_name,
            {
                "low": "run_general_agent",
                "medium": "run_general_agent",
                "high": "run_customer_escalation_summary",
            }
        )

        graph.add_edge("prepare_query", "extract_intent")
        graph.add_conditional_edges(
            "extract_intent",
            self.handle_intent,
            {
                "general_agent": "run_general_agent",
                "customer_escalation_summary": "extract_customer_name",
                "both": "extract_customer_name_for_both",
                "none": "none",
            },
        )
        
        graph.add_edge("extract_customer_name_for_both", "run_general_agent")
        graph.add_edge("extract_customer_name_for_both", "extract_customer_name")
        graph.add_edge("run_general_agent", "synthesise_response")
        graph.add_edge("run_customer_escalation_summary", "synthesise_response")
        graph.add_edge("synthesise_response", END)
        graph.add_edge("none", END)

        self.graph = graph.compile()

    async def prepare_query(self, state: MasterGraphState) -> MasterGraphState:
        #user_message = state["messages"][-1].content
        return {}

    async def extract_customer_name(self, state: MasterGraphState) -> MasterGraphState:
        user_message = state["messages"][-1].content
        customer_name = await self.customer_name_llm.ainvoke(
                            [SystemMessage(content=_load_customer_name_extraction_prompt())]
                            + state["messages"]
                        )
        return {
            "customer_name": customer_name.customer_name,
            "customer_name_confidence": customer_name.confidence,
            "customer_name_reason": customer_name.reason,
        }


    def handle_customer_name(self, state: MasterGraphState) -> str:
        return state["customer_name_confidence"]


    async def extract_intent(self, state: MasterGraphState):
        user_message = state["messages"][-1].content

        decision = await self.intent_llm.ainvoke(
            [
                SystemMessage(content=_load_intent_prompt()),
                HumanMessage(content=user_message),
            ]
        )

        return {
            "intent": decision.intent
        }

    def handle_intent(self, state: MasterGraphState) -> str:
        return state["intent"]

    def extract_customer_name_for_both(self, state: MasterGraphState) -> dict:
        return {}

    async def run_general_agent(self, state: MasterGraphState) -> MasterGraphState:
        messages = state["messages"]
        general_agent_response = await self.general_react_agent.ainvoke({"messages": messages})  
        return {
            "general_agent_response": general_agent_response["messages"][-1].content
        }


    async def none(self, state: MasterGraphState) -> MasterGraphState:
        return {"response": "I'm sorry, I don't know how to help with that."}

    async def run_customer_escalation_summary(self, state: MasterGraphState) -> MasterGraphState:
        customer_escalation_summary_response = await self.customer_escalation_graph_object.run(customer_name=state["customer_name"])
        return {
            "customer_escalation_summary": customer_escalation_summary_response
        }

    async def synthesise_response(self, state):
        general = state.get("general_agent_response")
        escalation = state.get("customer_escalation_summary")

        if general and escalation:
            response = await self.llm.ainvoke([
                SystemMessage(content="Combine the general answer and escalation summary into one concise response."),
                HumanMessage(content=f"General answer:\n{general}\n\nEscalation summary:\n{escalation}")
            ])
            return {"response": response.content}

        return {"response": escalation or general or "I could not produce a response."}

    async def run(self, messages: list[BaseMessage]) -> MasterGraphState:
        return await self.graph.ainvoke({"messages": messages})
