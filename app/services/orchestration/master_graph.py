from langgraph.graph import StateGraph

from app.services.skills.customer_escalation_summary import (
    CustomerEscalationGraph,
    EscalationSummaryState,
)
from langchain_core.messages import BaseMessage
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from typing import Literal
from langgraph.graph import END
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from functools import lru_cache
from pathlib import Path
from app.core.config import PROJECT_ROOT
from app.cache.user_cache import get_user_cache
from app.cache.customer_cache import get_customer_cache
from pydantic import BaseModel, Field
from app.repos.issues import create_issue, update_issue_status, add_issue_update




from typing import Literal, Union
from pydantic import BaseModel, Field

from app.repos.issues import add_issue_update, create_issue, update_issue_status

INTENT_PROMPT_PATH = (PROJECT_ROOT / "app" / "prompts" / "intent_prompt.txt")
GENERAL_AGENT_SYSTEM_PROMPT_PATH = (PROJECT_ROOT / "app" / "prompts" / "general_agent_system_prompt.txt")


@lru_cache
def _load_intent_prompt() -> str:
    return INTENT_PROMPT_PATH.read_text(encoding="utf-8")

@lru_cache
def _load_general_agent_system_prompt() -> str:
    return GENERAL_AGENT_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

class CustomerResolution(BaseModel):
    customer_id: int | None
    customer_name: str | None
    confidence: Literal["low", "medium", "high"]
    reason: str


class UserAssignmentResolution(BaseModel):
    user_id: int | None
    full_name: str | None
    confidence: Literal["low", "medium", "high"]
    reason: str

class IntentDecision(BaseModel):
    intent: Literal["customer_escalation_summary", "general_agent", "customer_escalation_summary_and_general_agent", "none", "create_issue", "update_issue"]
    customer_name: str | None = None


class StatusUpdateAction(BaseModel):
    action_type: Literal["status_update"]
    issue_id: int
    status: Literal["open", "in_progress", "blocked", "resolved", "closed"]
    note: str | None = None


class IssueNoteAction(BaseModel):
    action_type: Literal["issue_update"]
    issue_id: int
    update_type: Literal[
        "triage",
        "investigation",
        "customer_update",
        "internal_note",
        "technical_note",
        "resolution",
    ]
    update_text: str

class MissingInfoAction(BaseModel):
    action_type: Literal["missing_info"]
    missing_fields: list[str]
    clarification_question: str


class IssueUpdateDecision(BaseModel):
    action: Union[StatusUpdateAction, IssueNoteAction, MissingInfoAction]

class CreateIssueAction(BaseModel):
    has_required_info: bool
    missing_fields: list[str] = Field(default_factory=list)
    clarification_question: str | None = None

    customer_id: int | None = None
    customer_match_confidence: Literal["high", "medium", "low", "none"] = "none"

    title: str | None = None
    description: str | None = None
    priority: Literal["low", "medium", "high", "critical"] | None = None
    assigned_to: int | None = None  

class MasterGraphState(TypedDict, total=False):
    intent: Literal["customer_escalation_summary", "general_agent", "customer_escalation_summary_and_general_agent", "none", "create_issue", "update_issue"]
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: int
    user_roles: list[str]
    authorized: Literal["authorized", "not_authorized"]
    customer_name: str
    customer_name_confidence: Literal["low", "medium", "high"]
    customer_name_reason: str
    customer_id: int | None
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
        self.customer_name_llm = llm.with_structured_output(CustomerResolution)
        self.user_assignment_llm = llm.with_structured_output(UserAssignmentResolution)
        self.issue_update_llm = llm.with_structured_output(IssueUpdateDecision)

        graph = StateGraph(MasterGraphState)
        graph.add_node("prepare_query", self.prepare_query)
        graph.add_node("extract_intent", self.extract_intent)
        graph.add_node("resolve_customer_name", self.resolve_customer_name)
        graph.add_node("customer_name_clarification", self.customer_name_clarification)
        graph.add_node("resolve_customer_name_for_both", self.resolve_customer_name_for_both)
        graph.add_node("run_general_agent", self.run_general_agent)
        graph.add_node("run_customer_escalation_summary", self.run_customer_escalation_summary)
        graph.add_node("synthesise_response", self.synthesise_response)
        graph.add_node("authorize_create_issue", self.authorize_create_issue)
        graph.add_node("authorize_update_issue", self.authorize_update_issue)
        graph.add_node("run_create_issue", self.run_create_issue)
        graph.add_node("run_update_issue", self.run_update_issue)
        graph.add_node("not_authorized", self.not_authorized)
        graph.add_node("none", self.none)
        
        graph.set_entry_point("prepare_query")
        graph.add_conditional_edges(
            "resolve_customer_name",
            self.handle_customer_name,
            {
                "low": "customer_name_clarification",
                "medium": "run_customer_escalation_summary",
                "high": "run_customer_escalation_summary",
            }
        )

        graph.add_edge("prepare_query", "extract_intent")
        graph.add_conditional_edges(
            "extract_intent",
            self.handle_intent,
            {
                "general_agent": "run_general_agent",
                "customer_escalation_summary": "resolve_customer_name",
                "customer_escalation_summary_and_general_agent": "resolve_customer_name_for_both",
                "create_issue": "authorize_create_issue",
                "update_issue": "authorize_update_issue",
                "none": "none",
            },
        )
        graph.add_conditional_edges(
            "authorize_create_issue",
            self.handle_authorize_create_issue,
            {
                "authorized": "run_create_issue",
                "not_authorized": "not_authorized",
            }
        )
        graph.add_conditional_edges(
            "authorize_update_issue",
            self.handle_authorize_update_issue,
            {
                "authorized": "run_update_issue",
                "not_authorized": "not_authorized",
            }
        )
        graph.add_edge("resolve_customer_name_for_both", "run_general_agent")
        graph.add_edge("resolve_customer_name_for_both", "resolve_customer_name")
        graph.add_edge("run_general_agent", "synthesise_response")
        graph.add_edge("run_customer_escalation_summary", "synthesise_response")
        graph.add_edge("customer_name_clarification", END)
        graph.add_edge("synthesise_response", END)
        graph.add_edge("run_create_issue", END)
        graph.add_edge("run_update_issue", END)
        graph.add_edge("not_authorized", END)
        graph.add_edge("none", END)

        self.graph = graph.compile()

    async def prepare_query(self, state: MasterGraphState) -> MasterGraphState:
        print("prepare_query")
        #user_message = state["messages"][-1].content
        return {}

    async def resolve_customer_name(
        self,
        state: MasterGraphState,
    ) -> dict:
        print("resolve_customer_name")
        customers = await get_customer_cache()

        customer_context = "\n".join(
            f"- {customer['id']}: {customer['name']}"
            for customer in customers
        )

        customer = await self.customer_name_llm.ainvoke(
            [
                SystemMessage(
                    content=f"""
                    Resolve the customer mentioned in the conversation.

                    Known customers:

                    {customer_context}

                    Rules:
                    - Resolve using only the known customer list.
                    - Minor spelling mistakes are allowed.
                    - Do not invent customers.
                    - If no customer can be confidently resolved, return null values.
                    """
                )
            ]
            + state["messages"]
        )

        return {
            "customer_id": customer.customer_id,
            "customer_name": customer.customer_name,
            "customer_name_confidence": customer.confidence,
            "customer_name_reason": customer.reason,
        }


    def handle_customer_name(self, state: MasterGraphState) -> str:
        return state["customer_name_confidence"]


    async def extract_intent(self, state: MasterGraphState):
        print("extract_intent")
        recent_messages = state["messages"][-5:]

        decision = await self.intent_llm.ainvoke(
            [
                SystemMessage(content=_load_intent_prompt()),
                *recent_messages,
            ]
        )

        return {
            "intent": decision.intent
        }

    def handle_intent(self, state: MasterGraphState) -> str:
        return state["intent"]

    def resolve_customer_name_for_both(self, state: MasterGraphState) -> dict:
        print("resolve_customer_name_for_both")
        return state["customer_name_confidence"]

    async def resolve_customer(self, state: MasterGraphState) -> dict:
        if state.get("customer_id") is not None:
            return {
                "customer_id": state["customer_id"],
                "confidence": state.get("customer_name_confidence", "high"),
                "clarification_question": None,
            }

        customers = await get_customer_cache()
        customer_context = "\n".join(
            f"- {customer['id']}: {customer['name']}"
            for customer in customers
        )

        customer = await self.customer_name_llm.ainvoke(
            [
                SystemMessage(
                    content=f"""
                    Resolve the customer for issue creation.

                    Known customers:

                    {customer_context}

                    Rules:
                    - Resolve using only the known customer list.
                    - Minor spelling mistakes are allowed.
                    - Do not invent customers.
                    - If no customer can be confidently resolved, return null values.
                    """
                )
            ]
            + state["messages"]
        )

        return {
            "customer_id": customer.customer_id,
            "confidence": customer.confidence,
            "clarification_question": (
                "Which customer would you like to create the issue for?"
                if customer.confidence == "low"
                else None
            ),
        }

    async def customer_name_clarification(self, state: MasterGraphState) -> MasterGraphState:
        print("customer_name_clarification")
        return {
            "response": "Which customer would you like to create the issue for?",
            "messages": [
                AIMessage(content="Which customer would you like to create the issue for?"),
            ],
        }

    async def resolve_assigned_user(self, state: MasterGraphState) -> dict:
        users = await get_user_cache()
        user_context = "\n".join(
            f"- {user['id']}: {user['full_name']} ({user['username']})"
            for user in users
        )

        assignee = await self.user_assignment_llm.ainvoke(
            [
                SystemMessage(
                    content=f"""
                    Resolve the assignee for issue creation, if one was mentioned.

                    Known users:

                    {user_context}

                    Rules:
                    - Resolve using only the known user list.
                    - If no assignee was mentioned, return null user_id with high confidence.
                    - If an assignee was mentioned but cannot be matched, use low confidence.
                    - Do not invent users.
                    """
                )
            ]
            + state["messages"]
        )

        return {
            "user_id": assignee.user_id,
            "confidence": assignee.confidence,
            "clarification_question": (
                "Who should this issue be assigned to?"
                if assignee.confidence == "low"
                else None
            ),
        }

    async def authorize_create_issue(self, state: MasterGraphState) -> MasterGraphState:
        print("authorize_create_issue")
        if "admin" in state["user_roles"]:
            return {"authorized": "authorized"}
        else:
            return {"authorized": "not_authorized"}

    async def authorize_update_issue(self, state: MasterGraphState) -> MasterGraphState:
        print("authorize_update_issue")
        if "admin" in state["user_roles"] or "support" in state["user_roles"]:
            return {"authorized": "authorized"}
        else:
            return {"authorized": "not_authorized"}

    async def handle_authorize_create_issue(self, state: MasterGraphState) -> str:
        return state["authorized"]
    
    async def handle_authorize_update_issue(self, state: MasterGraphState) -> str:
        return state["authorized"]

    async def not_authorized(self, state: MasterGraphState) -> MasterGraphState:
        print("not_authorized")
        return {"response": "I'm sorry, you are not authorized to perform this action."}

    async def run_create_issue(
        self,
        state: MasterGraphState,
    ) -> MasterGraphState:
        print("run_create_issue")
        user_id = state["user_id"]

        customer = await self.resolve_customer(state)

        if customer["confidence"] == "low":
            clarification = (
                customer["clarification_question"]
                or "Which customer would you like to create the issue for?"
            )

            return {
                "response": clarification,
                "messages": [
                    AIMessage(content=clarification),
                ],
            }

        assignee = await self.resolve_assigned_user(state)

        if assignee["confidence"] == "low":
            clarification = (
                assignee["clarification_question"]
                or "Who should this issue be assigned to?"
            )

            return {
                "response": clarification,
                "messages": [
                    AIMessage(content=clarification),
                ],
            }

        structured_llm = self.llm.with_structured_output(CreateIssueAction)

        action = await structured_llm.ainvoke(
            [
                (
                    "system",
                    """
                    Extract issue creation details.

                    Required:
                    - title
                    - priority

                    Optional:
                    - description

                    Rules:
                    - Create a concise title if one is implied.
                    - Use the user's wording where possible.
                    - If priority is not stated, use medium only if clearly implied.
                    - If required information is missing, ask a clarification question.
                    """
                ),
                *state["messages"],
            ]
        )

        missing_fields = []

        if not action.title:
            missing_fields.append("title")

        if action.priority is None:
            missing_fields.append("priority")

        if missing_fields:
            clarification = (
                action.clarification_question
                or (
                    "I need a bit more information before creating the issue: "
                    + ", ".join(missing_fields)
                    + "."
                )
            )

            return {
                "response": clarification,
                "messages": [
                    AIMessage(content=clarification),
                ],
            }

        result = await create_issue(
            customer_id=customer["customer_id"],
            title=action.title,
            description=action.description,
            priority=action.priority,
            assigned_to=assignee["user_id"],
            user_id=user_id,
        )

        if not result["success"]:
            return {
                "response": "Issue creation failed: " + result["message"],
                "messages": [
                    ("assistant", "Issue creation failed: " + result["message"]),
                ],
            }
        else:
            return {
                "response": "Issue created successfully: " + result["message"],
                "messages": [
                    ("assistant", result["message"]),
                ],
            }

    async def run_update_issue(self, state: MasterGraphState) -> MasterGraphState:
        print("run_update_issue")
        user_id = state["user_id"]
        messages = state["messages"]

        

        decision = await self.issue_update_llm.ainvoke(
            [
                (
                    "system",
                    """
                    You extract structured issue update actions.

                    Decide whether the user wants to:
                    1. update the issue status, or
                    2. add an issue update/note/comment.

                    Return only structured data.

                    Rules:
                    - Use status_update when the user wants to mark, close, reopen, block, resolve, or change the status of an issue.
                    - Use issue_update when the user wants to add a note, comment, update, investigation detail, customer update, technical note, or resolution note.
                    - Do not invent an issue_id. If no issue_id is present, use the most recent issue_id from conversation context if it is clearly available.
                    - Do not invent update text. Use the user's wording where possible.
                    """
                ),
                *messages,
            ]
        )

        action = decision.action

        if action.action_type == "status_update":
            result = await update_issue_status(
                issue_id=action.issue_id,
                status=action.status,
                user_id=user_id,
                note=action.note,
            )

        elif action.action_type == "issue_update":
            result = await add_issue_update(
                issue_id=action.issue_id,
                update_text=action.update_text,
                update_type=action.update_type,
                user_id=user_id,
            )
        elif action.action_type == "missing_info":
            return {
                "response": action.clarification_question,
                "messages": [
                    AIMessage(content=action.clarification_question),
                ],
            }
        else:
            result = {
                "success": False,
                "message": "Unsupported issue update action.",
            }

        return {
            "response": result["message"],
            "messages": [
                *messages,
                ("assistant", result["message"]),
            ],
        }

    async def run_general_agent(self, state: MasterGraphState) -> MasterGraphState:
        print("run_general_agent")
        messages = state["messages"]
        general_agent_response = await self.general_react_agent.ainvoke({"messages": messages})  
        return {
            "general_agent_response": general_agent_response["messages"][-1].content
        }


    async def none(self, state: MasterGraphState) -> MasterGraphState:
        print("none")
        return {"response": "I'm sorry, I don't know how to help with that."}

    async def run_customer_escalation_summary(self, state: MasterGraphState) -> MasterGraphState:
        print("run_customer_escalation_summary")
        customer_escalation_summary_response = await self.customer_escalation_graph_object.run(customer_name=state["customer_name"])
        return {
            "customer_escalation_summary": customer_escalation_summary_response
        }

    async def synthesise_response(self, state):
        print("synthesise_response")
        general = state.get("general_agent_response")
        escalation = state.get("customer_escalation_summary")

        if general and escalation:
            response = await self.llm.ainvoke([
                SystemMessage(content="Combine the general answer and escalation summary into one concise response."),
                HumanMessage(content=f"General answer:\n{general}\n\nEscalation summary:\n{escalation}")
            ])
            return {"response": response.content}

        return {"response": escalation or general or "I could not produce a response."}

    async def run(self, messages: list[BaseMessage], user_id: int, user_roles: list[str]) -> MasterGraphState:
        return await self.graph.ainvoke({"messages": messages, "user_id": user_id, "user_roles": user_roles})
