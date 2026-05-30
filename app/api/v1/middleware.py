from fastapi import Request
from fastapi.responses import RedirectResponse
from app.api.v1.endpoints.auth import SESSION_STORE

PUBLIC_PATHS = {
    "/login",
    "/auth/callback",
    "/logout",
    "/health",
}


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if path in PUBLIC_PATHS:
        return await call_next(request)

    session_id = request.cookies.get("session")

    if not session_id or not is_valid_session(session_id):
        return RedirectResponse("/login")

    return await call_next(request)    

def is_valid_session(session_id: str) -> bool:
    return session_id in SESSION_STORE