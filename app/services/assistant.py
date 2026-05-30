from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from app.core.session import SESSION_STORE
from app.schemas.assistant import AssistantResponse


class AssistantUnauthorizedError(Exception):
    """Raised when the caller has no valid session."""


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


class AssistantService:
    def __init__(self, general_agent):
        self.general_agent = general_agent

    async def get_response(
        self,
        message: str | None,
        session_id: str | None,
        history: list[dict] | None,
    ) -> AssistantResponse:
        if not session_id or session_id not in SESSION_STORE:
            raise AssistantUnauthorizedError()

        messages = _history_to_messages(history)
        if not messages and message and message.strip():
            messages = [HumanMessage(content=message.strip())]

        response = await self.general_agent.ainvoke({"messages": messages})
        text_response = response["messages"][-1].content

        return AssistantResponse(message=text_response)


assistant_service = None


def init_assistant_service(general_agent):
    global assistant_service
    assistant_service = AssistantService(general_agent=general_agent)
