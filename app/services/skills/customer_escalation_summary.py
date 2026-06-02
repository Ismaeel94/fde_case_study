import json
import operator
from functools import lru_cache
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.types import Overwrite
from pydantic import BaseModel

from app.services.orchestration.node_trace import NodeTrace, node_trace_update
from app.core.config import PROJECT_ROOT
from app.repos.customer import CustomerRepository

RISK_PROMPT_PATH = PROJECT_ROOT / "app" / "prompts" / "risk_assessment_prompt.txt"
RECOMMENDED_ACTIONS_PROMPT_PATH = (
    PROJECT_ROOT / "app" / "prompts" / "recommended_action_prompt.txt"
)
SUMMARY_PROMPT_PATH = PROJECT_ROOT / "app" / "prompts" / "summary_prompt.txt"
MISSING_INFO_PROMPT_PATH = PROJECT_ROOT / "app" / "prompts" / "missing_info_prompt.txt"


@lru_cache
def _load_missing_info_prompt() -> str:
    return MISSING_INFO_PROMPT_PATH.read_text(encoding="utf-8")


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


class MissingInfo(BaseModel):
    missing_info: list[str]
    info_level: Literal["low", "medium", "high"]


class EscalationSummaryState(TypedDict, total=False):
    node_traces: Annotated[list[NodeTrace], operator.add]
    user_id: int
    user_roles: list[str]
    customer_name: str
    customer_data: dict
    missing_info: dict
    risk_assessment: dict
    recommended_action: dict
    summary: str


class CustomerEscalationGraph:
    def __init__(self, llm, tools):
        self.llm = llm
        self.tools = tools
        self.risk_llm = llm.with_structured_output(RiskAssessment)
        self.missing_info_llm = llm.with_structured_output(MissingInfo)
        self.recommended_actions_llm = llm.with_structured_output(RecommendedAction)

        self.customer_repository = CustomerRepository()

        graph = StateGraph(EscalationSummaryState)
        graph.add_node("get_customer_data", self.get_customer_data)
        graph.add_node("identify_missing_info", self.identify_missing_info)
        graph.add_node("assess_risk", self.assess_risk)
        graph.add_node("recommend_action", self.recommend_action)
        graph.add_node("generate_summary", self.generate_summary)

        graph.set_entry_point("get_customer_data")
        graph.add_edge("get_customer_data", "identify_missing_info")
        graph.add_conditional_edges(
            "identify_missing_info",
            self.route_missing_info,
            {
                "low": "generate_summary",
                "medium": "assess_risk",
                "high": "assess_risk",
            },
        )
        graph.add_edge("assess_risk", "recommend_action")
        graph.add_edge("recommend_action", "generate_summary")
        graph.add_edge("generate_summary", END)

        self.graph = graph.compile()

    def _trace(
        self,
        state: EscalationSummaryState,
        node_name: str,
        *,
        tool_calls: list[dict] | None = None,
    ) -> dict:
        return node_trace_update(
            node_name=node_name,
            user_id=state["user_id"],
            user_roles=state["user_roles"],
            tool_calls=tool_calls,
        )

    async def get_customer_data(self, state: EscalationSummaryState) -> EscalationSummaryState:
        tool_input = {"customer_name": state["customer_name"]}
        customer_data = await self.customer_repository.get_customer_context(
            tool_input["customer_name"]
        )
        tool_calls = [
            {
                "tool_name": "get_customer_context",
                "tool_input": tool_input,
                "tool_output": customer_data,
            }
        ]
        return {
            **self._trace(state, "get_customer_data", tool_calls=tool_calls),
            "customer_data": customer_data,
        }

    async def identify_missing_info(self, state: EscalationSummaryState) -> EscalationSummaryState:
        customer_data = state["customer_data"]
        missing_info = await self.missing_info_llm.ainvoke(
            [
                SystemMessage(content=_load_missing_info_prompt()),
                HumanMessage(content=json.dumps(customer_data, indent=2, default=str)),
            ]
        )
        return {
            **self._trace(state, "identify_missing_info"),
            "missing_info": missing_info.model_dump(),
        }

    @staticmethod
    def route_missing_info(state: EscalationSummaryState) -> str:
        return state["missing_info"]["info_level"]

    async def assess_risk(self, state: EscalationSummaryState) -> EscalationSummaryState:
        assessment = await self.risk_llm.ainvoke(
            [
                SystemMessage(content=_load_risk_assessment_prompt()),
                HumanMessage(
                    content=json.dumps(state["customer_data"], indent=2, default=str)
                ),
            ]
        )
        return {
            **self._trace(state, "assess_risk"),
            "risk_assessment": assessment.model_dump(),
        }

    async def recommend_action(self, state: EscalationSummaryState) -> EscalationSummaryState:
        information = {
            "customer_data": state["customer_data"],
            "risk_assessment": state["risk_assessment"],
        }
        action = await self.recommended_actions_llm.ainvoke(
            [
                SystemMessage(content=_load_recommended_actions_prompt()),
                HumanMessage(content=json.dumps(information, indent=2, default=str)),
            ]
        )
        return {
            **self._trace(state, "recommend_action"),
            "recommended_action": action.model_dump(),
        }

    async def generate_summary(self, state: EscalationSummaryState) -> EscalationSummaryState:
        information = {
            "customer_data": state["customer_data"],
            "missing_info": state.get("missing_info"),
            "risk_assessment": state.get("risk_assessment"),
            "recommended_action": state.get("recommended_action"),
        }
        summary = await self.llm.ainvoke(
            [
                SystemMessage(content=_load_summary_prompt()),
                HumanMessage(content=json.dumps(information, indent=2, default=str)),
            ]
        )
        return {
            **self._trace(state, "generate_summary"),
            "summary": summary.content,
        }

    async def run(
        self,
        customer_name: str,
        user_id: int,
        user_roles: list[str],
    ) -> EscalationSummaryState:
        return await self.graph.ainvoke(
            {
                "customer_name": customer_name,
                "user_id": user_id,
                "user_roles": user_roles,
                "node_traces": Overwrite([]),
            }
        )
