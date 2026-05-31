from typing import Literal, TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_core.tools import Tool
from app.services.mcp_client import postgres_mcp_tools
from langchain_core.tools import Tool
from langchain_mcp_adapters.tools import load_mcp_tools
from app.core.config import PROJECT_ROOT, settings
from app.repos.customer import CustomerRepository
from app.services.mcp_client import call_postgres_tool
from langgraph.graph import END
from functools import lru_cache

from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
import json



RISK_PROMPT_PATH = (PROJECT_ROOT / "app" / "prompts" / "risk_assessment_prompt.txt")
RECOMMENDED_ACTIONS_PROMPT_PATH = (PROJECT_ROOT / "app" / "prompts" / "recommended_action_prompt.txt")
SUMMARY_PROMPT_PATH = (PROJECT_ROOT / "app" / "prompts" / "summary_prompt.txt")



@lru_cache
def _load_risk_assessment_prompt() -> str:
    return RISK_PROMPT_PATH.read_text(encoding="utf-8") 

@lru_cache
def _load_recommended_actions_prompt() -> str:
    return RECOMMENDED_ACTIONS_PROMPT_PATH.read_text(encoding="utf-8")

@lru_cache
def _load_summary_prompt() -> str:
    return SUMMARY_PROMPT_PATH.read_text(encoding="utf-8")

class RecommendedAction(BaseModel):
    recommended_action: str
    update_type: Literal[
        "triage",
        "investigation",
        "customer_update",
        "internal_note",
        "technical_note",
        "resolution",
    ]
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    rationale: str
    target_issue_ids: list[int]
    requires_human_review: bool

class RiskAssessment(BaseModel):
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    rationale: str
    evidence: list[str]
    missing_information: list[str]

class EscalationSummaryState(TypedDict):
    customer_name: str
    customer_data: list[dict]
    risk_assessment: RiskAssessment
    recommended_action: RecommendedAction
    missing_information: list[str]
    summary: str

class CustomerEscalationGraph():

    def __init__(self, llm, tools):
        self.llm = llm
        self.tools = tools
        self.risk_llm = llm.with_structured_output(RiskAssessment)
        self.recommended_actions_llm = llm.with_structured_output(RecommendedAction)

        self.customer_repository = CustomerRepository()

        graph = StateGraph(EscalationSummaryState)
        graph.add_node("get_customer_data", self.get_customer_data)
        graph.add_node("assess_risk", self.assess_risk)
        graph.add_node("recommend_action", self.recommend_action)
        graph.add_node("generate_summary", self.generate_summary)

        graph.set_entry_point("get_customer_data")
        graph.add_edge("get_customer_data", "assess_risk")
        graph.add_edge("assess_risk", "recommend_action")
        graph.add_edge("recommend_action", "generate_summary")
        graph.add_edge("generate_summary", END)

        self.graph = graph.compile()

    async def get_customer_data(self, state: EscalationSummaryState) -> EscalationSummaryState:
        customer_data = await self.customer_repository.get_customer_context(state["customer_name"])
        return {"customer_data":customer_data or {}}

    async def assess_risk(self, state: EscalationSummaryState) -> EscalationSummaryState:
        assessment = await self.risk_llm.ainvoke(
            [
                SystemMessage(content=_load_risk_assessment_prompt()),
                HumanMessage(content=json.dumps(state["customer_data"], indent=2))
            ]
        )
        return {"risk_assessment": assessment}

    async def recommend_action(self, state: EscalationSummaryState) -> EscalationSummaryState:
        customer_data = state["customer_data"]
        risk_assessment = state["risk_assessment"]
        information = {
            "customer_data": customer_data,
            "risk_assessment": risk_assessment.model_dump()
        }
        action = await self.recommended_actions_llm.ainvoke(
            [
                SystemMessage(content=_load_recommended_actions_prompt()),
                HumanMessage(content=json.dumps(information, indent=2))
            ]
        )
        return {"recommended_action": action}

    async def generate_summary(self, state: EscalationSummaryState) -> EscalationSummaryState:
        customer_data = state["customer_data"]
        risk_assessment = state["risk_assessment"]
        recommended_action = state["recommended_action"]
        information = {
            "customer_data": customer_data,
            "risk_assessment": risk_assessment.model_dump(),
            "recommended_action": recommended_action.model_dump()
        }
        summary = await self.llm.ainvoke([
                SystemMessage(content=_load_summary_prompt()),
                HumanMessage(content=json.dumps(information, indent=2))
            ])
        return {"summary": summary.content}
        

    async def run(self, customer_name: str) -> EscalationSummaryState:
        return await self.graph.ainvoke({"customer_name": customer_name})

        