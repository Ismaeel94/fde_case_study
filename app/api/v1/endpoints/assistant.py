from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi import Depends
from app.services.assistant import AssistantUnauthorizedError
from app.schemas.assistant import AssistantResponse

from app.api.deps import get_assistant_service
from app.services.assistant import AssistantService

router = APIRouter(tags=["assistant"])


@router.get("/messages")
def messages(
    http_request: Request,
    message: str | None = None,
    assistant_service: AssistantService = Depends(get_assistant_service),
) -> AssistantResponse:
    try:
        return assistant_service.get_response(
            message,
            http_request.cookies.get("session"),
        )
    except AssistantUnauthorizedError:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/")
def home():
    return RedirectResponse(url="/assistant")
