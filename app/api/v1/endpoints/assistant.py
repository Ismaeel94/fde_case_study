from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.api.v1.endpoints.auth import SESSION_STORE
from app.schemas.assistant import AssistantRequest, AssistantResponse

router = APIRouter(tags=["assistant"])


@router.get("/assistant")
def assistant(
    http_request: Request,
    message: str | None = "Default message",
) -> AssistantResponse:
    session_id = http_request.cookies.get("session")
    if not session_id or session_id not in SESSION_STORE:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session = SESSION_STORE[session_id]
    name = session.get("username") or assistant_request.message or "guest"
    return AssistantResponse(message=f"Hello, {name}! I am the assistant.")


@router.get("/")
def home():
    return RedirectResponse(url="/assistant")




