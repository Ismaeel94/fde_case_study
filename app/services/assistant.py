import logging
from functools import lru_cache
from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

import app.core.session as sess
from app.schemas.assistant import AssistantResponse
from app.api.llms.llms import get_llm
from app.services.skills.customer_escalation_summary import CustomerEscalationGraph
from app.services.orchestration.master_graph import MasterGraph
from app.core.config import settings


logger = logging.getLogger(__name__)

GENERAL_AGENT_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "general_agent_system_prompt.txt"
)


class AssistantUnauthorizedError(Exception):
    """Raised when the caller has no valid session."""


@lru_cache
def _load_general_agent_system_prompt() -> str:
    return GENERAL_AGENT_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _history_to_messages(history: list[dict] | None) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for item in history or []:
        role = item.get("role")
        content = item.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


def _build_agent_messages(
    message: str | None,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    if message and message.strip():
        messages.append(HumanMessage(content=message.strip()))
    return messages

class AssistantService:
    def __init__(self, llm, tools):
        self.llm = llm
        self.tools = tools
        self.master_graph = MasterGraph(llm=llm, tools=tools)

    async def get_response(
        self,
        message: str | None,
        session_id: str | None
    ) -> AssistantResponse:
        logger.info("session_id: %s", session_id)
        session = await sess.session_store.get_session(session_id)
        if not session_id or await sess.session_store.get_session(session_id) is None:
            logger.error("session_id not found")
            raise AssistantUnauthorizedError()

        session_user_id = session.get("user_id")
        session_user_roles = session.get("roles")
        logger.info("session_user_roles: %s", session_user_roles)

        messages = _build_agent_messages(message)

        pending_interrupt = await sess.session_store.get_session_value(session_id, "pending_interrupt")
        logger.info("pending_interrupt: %s", pending_interrupt)

        if (settings.EVALUATE_MODE):
            pending_interrupt = None

        if pending_interrupt:
            if message.lower() in ["approve", "yes", "confirm"]:
                response = await self.master_graph.resume(
                    session_id=session_id,
                    decision="yes",
                )
                await sess.session_store.set_session_value(session_id, "pending_interrupt", None)
            else:
                response = await self.master_graph.resume(
                    session_id=session_id,
                    decision="no",
                )
                await sess.session_store.set_session_value(session_id, "pending_interrupt", None)
        else:
           response = await self.master_graph.run(messages, session_id, session_user_id, session_user_roles)

        return AssistantResponse(
            message=str(response.get("response") or response.get("final_response", ""))
        )


assistant_service = None


def init_assistant_service(tools):
    global assistant_service
    assistant_service = AssistantService(llm=get_llm(), tools=tools)
