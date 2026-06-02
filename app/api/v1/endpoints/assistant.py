from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi import Depends
from app.services.assistant import AssistantUnauthorizedError
from app.schemas.assistant import AssistantResponse

from app.api.deps import get_assistant_service
from app.services.assistant import AssistantService
from pydantic import BaseModel


router = APIRouter(tags=["assistant"])



class MessageRequest(BaseModel):
    message: str

@router.post("/messages")
async def messages(
    http_request: Request,
    request: MessageRequest,
    assistant_service: AssistantService = Depends(get_assistant_service),
) -> AssistantResponse:
    try:
        print(f"message in endpoint: {request.message}")

        return await assistant_service.get_response(
            request.message,
            http_request.cookies.get("session"),
        )

    except AssistantUnauthorizedError:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/")
def home():
    return RedirectResponse(url="/assistant")
