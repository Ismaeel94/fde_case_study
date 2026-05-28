from fastapi import Request
from fastapi.responses import RedirectResponse


async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/assistant"):
        if not request.cookies.get("session"):
            return RedirectResponse("/login")
    return await call_next(request)