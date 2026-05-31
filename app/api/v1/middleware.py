from fastapi import Request
from fastapi.responses import RedirectResponse
import app.core.session as sess


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

    if not session_id or not await is_valid_session(session_id):
        return RedirectResponse("/login")

    return await call_next(request)    

async def is_valid_session(session_id: str) -> bool:
    return await sess.session_store.get_session(session_id) is not None