from pydantic import BaseModel


class AssistantRequest(BaseModel):
    message: str | None = None


class AssistantResponse(BaseModel):
    message: str
