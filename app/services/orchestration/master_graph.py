import json
import logging
import operator

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from langgraph.types import interrupt, Command, Send
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from typing import Annotated, Literal, TypedDict, Union
from functools import lru_cache
import langsmith
from langgraph.types import Overwrite
from app.services.skills.customer_escalation_summary import CustomerEscalationGraph
from app.core.config import PROJECT_ROOT
from app.cache.user_cache import get_user_cache
from app.cache.customer_cache import get_customer_cache
from pydantic import BaseModel, Field
from app.repos.issues import add_issue_update, create_issue, update_issue_status
import app.core.session as sess
from app.eval.eval_tools import extract_tool_calls_for_react_agent
from app.eval.node_trace_store import persist_run_trace
from app.services.orchestration.node_trace import NodeTrace, node_trace_update


logger = logging.getLogger(__name__)


checkpointer: AsyncRedisSaver | None = None
INTENT_PROMPT_PATH = (PROJECT_ROOT / "app" / "prompts" / "intent_prompt.txt")
GENERAL_AGENT_SYSTEM_PROMPT_PATH = (PROJECT_ROOT / "app" / "prompts" / "general_agent_system_prompt.txt")
PREPARE_SUBQUERIES_PROMPT_PATH = (PROJECT_ROOT / "app" / "prompts" / "prepare_subqueries_prompt.txt")
SYNTHESISE_RESPONSE_PROMPT_PATH = (PROJECT_ROOT / "app" / "prompts" / "systhesiser_prompt.txt")

@lru_cache
def _load_synthesise_response_prompt() -> str:
    return SYNTHESISE_RESPONSE_PROMPT_PATH.read_text(encoding="utf-8")

@lru_cache
def _load_prepare_subqueries_prompt() -> str:
    return PREPARE_SUBQUERIES_PROMPT_PATH.read_text(encoding="utf-8")

@lru_cache
def _load_intent_prompt() -> str:
    return INTENT_PROMPT_PATH.read_text(encoding="utf-8")

@lru_cache
def _load_general_agent_system_prompt() -> str:
    return GENERAL_AGENT_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

class ExtractedIntents(BaseModel):
    intents: list[
        Literal[
            "customer_escalation_summary",
            "general_agent",
            "none",
            "create_issue",
            "update_issue",
        ]
    ]

class IntentTask(BaseModel):
    intent: Literal[
        "customer_escalation_summary",
        "general_agent",
        "none",
        "create_issue",
        "update_issue",
    ]
    query: str


class IntentTasks(BaseModel):
    tasks: list[IntentTask]

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
    node_traces: Annotated[list[NodeTrace], operator.add]
    intents: dict
    tasks: dict
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: int
    user_roles: list[str]
    authorized: Literal["authorized", "not_authorized"]
    responses: Annotated[list[dict], operator.add]
    final_response: str
    response: str


def node_trace_update_from_state(
    state: MasterGraphState,
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


class MasterGraph:
    def __init__(self, llm, tools):
        self.llm = llm
        self.tools = tools
        self.intent_llm = llm.with_structured_output(ExtractedIntents)
        self.intent_tasks_llm = llm.with_structured_output(IntentTasks)
        self.general_react_agent = create_react_agent(model=llm, tools=tools, prompt=_load_general_agent_system_prompt())   
        self.customer_escalation_graph_object = CustomerEscalationGraph(llm=llm, tools=tools)
        self.customer_name_llm = llm.with_structured_output(CustomerResolution)
        self.user_assignment_llm = llm.with_structured_output(UserAssignmentResolution)
        self.issue_update_llm = llm.with_structured_output(IssueUpdateDecision)

        graph = StateGraph(MasterGraphState)
        graph.add_node("extract_intents", self.extract_intents)
        graph.add_node("prepare_subqueries", self.prepare_subqueries)
        graph.add_node("run_general_agent", self.run_general_agent)
        graph.add_node("run_customer_escalation_summary", self.run_customer_escalation_summary)
        graph.add_node("synthesise_response", self.synthesise_response)
        graph.add_node("authorize_create_issue", self.authorize_create_issue)
        graph.add_node("authorize_update_issue", self.authorize_update_issue)
        graph.add_node("run_create_issue", self.run_create_issue)
        graph.add_node("run_update_issue", self.run_update_issue)
        graph.add_node("not_authorized_create_issue", self.not_authorize_create_issue)
        graph.add_node("not_authorized_update_issue", self.not_authorize_update_issue)
        graph.add_node("none", self.none)
        
        graph.set_entry_point("extract_intents")
        

        graph.add_edge("extract_intents", "prepare_subqueries")
        graph.add_conditional_edges(
            "prepare_subqueries",
            self.route_tasks
        )
        graph.add_conditional_edges(
            "authorize_create_issue",
            self.handle_authorize_create_issue,
            {
                "authorized": "run_create_issue",
                "not_authorized": "not_authorized_create_issue",
            }
        )
        graph.add_conditional_edges(
            "authorize_update_issue",
            self.handle_authorize_update_issue,
            {
                "authorized": "run_update_issue",
                "not_authorized": "not_authorized_update_issue",
            }
        )

        
        graph.add_edge("run_customer_escalation_summary", "synthesise_response")
        graph.add_edge("run_general_agent", "synthesise_response")
        graph.add_edge("run_create_issue", "synthesise_response")
        graph.add_edge("run_update_issue", "synthesise_response")
        graph.add_edge("not_authorized_create_issue", "synthesise_response")
        graph.add_edge("not_authorized_update_issue", "synthesise_response")
        graph.add_edge("none", "synthesise_response")

        graph.add_edge("synthesise_response", END)

        self.graph = graph.compile(checkpointer=checkpointer)

    async def _customer_name(self, customer_id: int | None) -> str:
        if customer_id is None:
            return "Unknown"
        for customer in await get_customer_cache():
            if customer["id"] == customer_id:
                return customer["name"]
        return str(customer_id)

    async def _user_name(self, user_id: int | None) -> str:
        if user_id is None:
            return "Unassigned"
        for user in await get_user_cache():
            if user["id"] == user_id:
                return user["full_name"]
        return str(user_id)

    async def prepare_subqueries(self, state: MasterGraphState) -> MasterGraphState:
        logger.info("prepare_subqueries")
        intents = state["intents"]
        window = state["messages"][-5:]
        tasks = await self.intent_tasks_llm.ainvoke(
            [
                SystemMessage(content=_load_prepare_subqueries_prompt()),
                *window,
            ]
        )
        return {
            **node_trace_update_from_state(state, "prepare_subqueries"),
            "tasks": tasks.model_dump(),
        }

    @staticmethod
    def route_tasks(state: MasterGraphState):
        sends = []
        tasks = state["tasks"]["tasks"]
        if tasks is None or len(tasks) == 0:
            tasks =  [{"intent": "none", "query": "No tasks to perform"}]

        for task in tasks:
            intent = task["intent"]
            if intent == "customer_escalation_summary":
                sends.append(Send("run_customer_escalation_summary", state))

            elif intent == "general_agent":
                sends.append(Send("run_general_agent", state))

            elif intent == "create_issue":
                sends.append(Send("authorize_create_issue", state))

            elif intent == "update_issue":
                sends.append(Send("authorize_update_issue", state))

            elif intent == "none":
                sends.append(Send("none", state))

        return sends




    async def extract_intents(self, state: MasterGraphState):
        logger.info("extract_intents")
        recent_messages = state["messages"][-5:]

        intents = await self.intent_llm.ainvoke(
            [
                SystemMessage(content=_load_intent_prompt()),
                *recent_messages,
            ]
        )

        return {
            **node_trace_update_from_state(state, "extract_intents"),
            "intents": intents.model_dump(),
        }

    async def resolve_customer(self, state: MasterGraphState) -> dict:
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
            "customer_name": customer.customer_name,
            "customer_id": customer.customer_id,
            "confidence": customer.confidence,
            "clarification_question": (
                "Could you please provide the correct customer name?"
                if customer.confidence == "low"
                else None
            ),
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
        logger.info("authorize_create_issue")
        if "admin" in state["user_roles"]:
            return {
                **node_trace_update_from_state(state, "authorize_create_issue"),
                "authorized": "authorized",
            }
        return {
            **node_trace_update_from_state(state, "authorize_create_issue"),
            "authorized": "not_authorized",
        }

    async def authorize_update_issue(self, state: MasterGraphState) -> MasterGraphState:
        logger.info("authorize_update_issue")
        if "admin" in state["user_roles"] or "support" in state["user_roles"]:
            return {
                **node_trace_update_from_state(state, "authorize_update_issue"),
                "authorized": "authorized",
            }
        return {
            **node_trace_update_from_state(state, "authorize_update_issue"),
            "authorized": "not_authorized",
        }

    async def handle_authorize_create_issue(self, state: MasterGraphState) -> str:
        return state["authorized"]
    
    async def handle_authorize_update_issue(self, state: MasterGraphState) -> str:
        return state["authorized"]

    async def not_authorize_create_issue(self, state: MasterGraphState) -> MasterGraphState:
        logger.info("not_authorized_create_issue")
        return {
            **node_trace_update_from_state(state, "not_authorized_create_issue"),
            "responses": [
                {
                    "intent": "create_issue",
                    "response": "I'm sorry, you are not authorized to create issues.",
                }
            ],
        }

    async def not_authorize_update_issue(self, state: MasterGraphState) -> MasterGraphState:
        logger.info("not_authorized_update_issue")
        return {
            **node_trace_update_from_state(state, "not_authorized_update_issue"),
            "responses": [
                {
                    "intent": "update_issue",
                    "response": "I'm sorry, you are not authorized to update issues.",
                }
            ],
        }        

    async def run_create_issue(
        self,
        state: MasterGraphState,
    ) -> MasterGraphState:
        logger.info("run_create_issue")
        user_id = state["user_id"]
        tool_calls: list[dict] = []

        customer = await self.resolve_customer(state)
        tool_calls.append(
            {
                "tool_name": "resolve_customer",
                "tool_input": "state",
                "tool_output": customer,
            }
        )

        if customer["confidence"] == "low":
            clarification = (
                customer["clarification_question"]
                or "Which customer would you like to create the issue for?"
            )

            return {
                **node_trace_update_from_state(
                    state, "run_create_issue", tool_calls=tool_calls
                ),
                "responses": [
                    {
                        "intent": "create_issue",
                        "response": "Clarification: " + clarification,
                    }
                ],
            }

        assignee = await self.resolve_assigned_user(state)
        tool_calls.append(
            {
                "tool_name": "resolve_assigned_user",
                "tool_input": "state",
                "tool_output": assignee,
            }
        )

        if assignee["confidence"] == "low":
            clarification = (
                assignee["clarification_question"]
                or "Who should this issue be assigned to?"
            )

            return {
                **node_trace_update_from_state(
                    state, "run_create_issue", tool_calls=tool_calls
                ),
                "responses": [
                    {
                        "intent": "create_issue",
                        "response": "Clarification: " + clarification,
                    }
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
                **node_trace_update_from_state(
                    state, "run_create_issue", tool_calls=tool_calls
                ),
                "responses": [
                    {
                        "intent": "create_issue",
                        "response": "Clarification: " + clarification,
                    }
                ],
            }


        customer_name = await self._customer_name(customer["customer_id"])
        assignee_name = await self._user_name(assignee["user_id"])
        created_by_name = await self._user_name(user_id)

        approval = interrupt(
            "Create issue with these details? (yes/no)\n\n"
            + f"Title: {action.title}\n"
            + f"Description: {action.description}\n"
            + f"Priority: {action.priority}\n"
            + f"Assigned to: {assignee_name}\n"
            + f"Customer: {customer_name}\n"
            + f"Created by: {created_by_name}\n"
        )

        logger.info("approval: %s", approval)
        if approval.lower().strip() != "yes":
            return {
                **node_trace_update_from_state(
                    state, "run_create_issue", tool_calls=tool_calls
                ),
                "responses": [
                    {
                        "intent": "create_issue",
                        "response": "Issue creation cancelled.",
                    }
                ],
            }

        create_issue_input = {
            "customer_id": customer["customer_id"],
            "title": action.title,
            "description": action.description,
            "priority": action.priority,
            "assigned_to": assignee["user_id"],
            "user_id": user_id,
        }
        result = await create_issue(**create_issue_input)
        tool_calls.append(
            {
                "tool_name": "create_issue",
                "tool_input": create_issue_input,
                "tool_output": result,
            }
        )

        if not result["success"]:
            return {
                **node_trace_update_from_state(
                    state, "run_create_issue", tool_calls=tool_calls
                ),
                "responses": [
                    {
                        "intent": "create_issue",
                        "response": "Issue creation failed: " + result["message"],
                    }
                ],
            }
        return {
            **node_trace_update_from_state(
                state, "run_create_issue", tool_calls=tool_calls
            ),
            "responses": [
                {
                    "intent": "create_issue",
                    "response": "Issue created successfully: " + result["message"],
                }
            ],
        }


    async def run_update_issue(self, state: MasterGraphState) -> MasterGraphState:
        logger.info("run_update_issue")
        trace = node_trace_update_from_state(state, "run_update_issue")
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
            user_name = await self._user_name(user_id)
            approval = interrupt(
                "Update issue status with these details? (yes/no)\n\n"
                + f"Status: {action.status}\n"
                + f"Note: {action.note}\n"
                + f"User: {user_name}\n"
                + f"Issue: {action.issue_id}\n"
            )
            logger.info("approval: %s", approval)
            if approval.lower().strip() != "yes":
                return {
                    **trace,
                    "responses": [
                        {
                            "intent": "update_issue",
                            "response": "Issue status update cancelled.",
                        }
                    ],
                }

                

            result = await update_issue_status(
                issue_id=action.issue_id,
                status=action.status,
                user_id=user_id,
                note=action.note,
            )

        elif action.action_type == "issue_update":
            user_name = await self._user_name(user_id)
            approval = interrupt(
                "Add issue update with these details? (yes/no)\n\n"
                + f"Update text: {action.update_text}\n"
                + f"Update type: {action.update_type}\n"
                + f"User: {user_name}\n"
                + f"Issue: {action.issue_id}\n"
            )
            logger.info("approval: %s", approval)
            if approval.lower().strip() != "yes":
                return {
                    **trace,
                    "responses": [
                        {
                            "intent": "update_issue",
                            "response": "Issue status update cancelled.",
                        }
                    ],
                }


            result = await add_issue_update(
                issue_id=action.issue_id,
                update_text=action.update_text,
                update_type=action.update_type,
                user_id=user_id,
            )
        elif action.action_type == "missing_info":
            return {
                **trace,
                "responses": [
                    {
                        "intent": "update_issue",
                        "response": "Clarification: " + action.clarification_question,
                    }
                ],
            }
        else:
            result = {
                "success": False,
                "message": "Unsupported issue update action.",
            }

        return {
            **trace,
            "responses": [
                {
                    "intent": "update_issue",
                    "response": result["message"],
                }
            ],
        }

        

    async def run_general_agent(self, state: MasterGraphState) -> MasterGraphState:
        logger.info("run_general_agent")
        messages = state["messages"]
        general_agent_response = await self.general_react_agent.ainvoke({"messages": messages})  
       

        tool_calls = extract_tool_calls_for_react_agent(general_agent_response["messages"])
        logger.info("tool_calls: %s", tool_calls)

        return {
            **node_trace_update_from_state(
                state, "run_general_agent", tool_calls=tool_calls
            ),
            "responses": [
                {
                    "intent": "general_agent",
                    "response": general_agent_response["messages"][-1].content,
                }
            ],
        }


    async def none(self, state: MasterGraphState) -> MasterGraphState:
        logger.info("none")
        return {
            **node_trace_update_from_state(state, "none"),
            "responses": [
                {
                    "intent": "none",
                    "response": "I'm sorry, I don't know how to help with that.",
                }
            ],
        }

    async def run_customer_escalation_summary(self, state: MasterGraphState) -> MasterGraphState:
        logger.info("run_customer_escalation_summary")
        customer = await self.resolve_customer(state)
        tool_calls = [
            {
                "tool_name": "resolve_customer",
                "tool_input": "state",
                "tool_output": customer,
            }
        ]

        if customer["confidence"] == "low":
            clarification = (
                customer["clarification_question"]
                or "Could you please provide the correct customer name for the summary?"
            )

            return {
                **node_trace_update_from_state(
                    state,
                    "run_customer_escalation_summary",
                    tool_calls=tool_calls,
                ),
                "responses": [
                    {
                        "intent": "escalation_summary",
                        "response": "Clarification: " + clarification,
                    }
                ],
            }


        customer_escalation_summary_response = await self.customer_escalation_graph_object.run(
            customer_name=customer["customer_name"],
            user_id=state["user_id"],
            user_roles=state["user_roles"],
        )
        summary = customer_escalation_summary_response.get("summary")
        subgraph_traces = customer_escalation_summary_response.get("node_traces") or []
        if not summary:
            summary = json.dumps(customer_escalation_summary_response, default=str)

        master_trace = node_trace_update_from_state(
            state,
            "run_customer_escalation_summary",
            tool_calls=tool_calls,
        )
        return {
            "node_traces": master_trace["node_traces"] + subgraph_traces,
            "responses": [
                {
                    "intent": "customer_escalation_summary",
                    "response": summary,
                }
            ],
        }

    async def synthesise_response(self, state):
        logger.info("synthesise_response")

        # task_count = len(state["tasks"]["tasks"])
        # if len(state.get("responses", [])) < task_count:
        #     raise RuntimeError("Synthesis reached before all task responses were ready.")

        content = json.dumps(
                    {
                        "tasks": state["tasks"],
                        "responses": state["responses"],
                    },
                    indent=2,
                    default=str,
                )

        logger.debug("synthesise content: %s", content)

        response = await self.llm.ainvoke([
            SystemMessage(content=_load_synthesise_response_prompt()),
            HumanMessage(
                content=content
            ),
        ])



        return {
            **node_trace_update_from_state(state, "synthesise_response"),
            "final_response": response.content,
            "response": response.content,
            "messages": [AIMessage(content=response.content)],
        }


    @langsmith.traceable()
    async def run(
        self,
        messages: list[BaseMessage],
        session_id: str,
        user_id: int,
        user_roles: list[str],
    ) -> MasterGraphState:
        config = {"configurable": {"thread_id": session_id}}

        result = await self.graph.ainvoke(
            {
                "messages": messages,
                "user_id": user_id,
                "user_roles": user_roles,
                "responses": Overwrite([]),
                "node_traces": Overwrite([]),
            },
            config=config,
        )

        if checkpointer is not None:
            snapshot = await self.graph.aget_state(config)
            logger.info("snapshot interrupts: %s", snapshot.interrupts)

            if snapshot.interrupts:
                interrupt_payload = snapshot.interrupts[0].value
                await sess.session_store.set_session_value(
                    session_id,
                    "pending_interrupt",
                    {
                        "type": "approval_required",
                        "thread_id": session_id,
                    },
                )

                return {
                    "response": interrupt_payload,
                }

        node_traces = result.get("node_traces") or []
        final_response = result.get("final_response") or result.get("response")
        trace_file = persist_run_trace(
            graph_input=messages,
            graph_output=final_response,
            node_traces=node_traces,
        )
        if trace_file is not None:
            logger.info(
                "Wrote run trace (%d node(s)) to %s",
                len(node_traces),
                trace_file,
            )

        return {
            **result,
            "response": result.get("response") or result.get("final_response", ""),
        }

    async def resume(self, session_id: str, decision: str):
        config = {"configurable": {"thread_id": session_id}}

        result = await self.graph.ainvoke(
            Command(resume=decision),
            config=config,
        )
        return {
            **result,
            "response": result.get("response") or result.get("final_response", ""),
        }


async def init_checkpointer(cp: AsyncRedisSaver | None) -> None:
    global checkpointer
    checkpointer = cp
