from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt

from app.core.config import settings
from app.core.session import SESSION_STORE
from app.schemas.assistant import AssistantRequest

router = APIRouter(tags=["auth"])


@router.get("/login")
def login():
    auth_url = (
        f"{settings.KEYCLOAK_BASE_URL}/realms/{settings.REALM}/protocol/openid-connect/auth"
        f"?client_id={settings.CLIENT_ID}"
        f"&response_type=code"
        f"&scope=openid profile email"
        f"&redirect_uri={settings.KEY_CLOAK_REDIRECT_URI}"
    )
    return RedirectResponse(auth_url)


@router.get("/auth/callback")
async def auth_callback(code: str):

    print(f"Callback endpoint called")
    token_url = (
        f"{settings.KEYCLOAK_BASE_URL}/realms/{settings.REALM}/protocol/openid-connect/token"
    )

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.CLIENT_ID,
                "client_secret": settings.CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.KEY_CLOAK_REDIRECT_URI,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
        )

    if token_response.status_code != 200:
        raise HTTPException(status_code=401, detail="Token exchange failed")

    tokens = token_response.json()
    access_token = tokens["access_token"]
    id_token = tokens["id_token"]

    id_claims = await verify_keycloak_jwt(id_token, access_token=access_token)
    access_claims = await verify_keycloak_jwt(access_token, verify_audience=False)


    session = {
        "sub": id_claims["sub"],
        "email": id_claims.get("email"),
        "username": id_claims.get("preferred_username"),
        "roles": access_claims.get("realm_access", {}).get("roles", []),
    }

    session_id = str(uuid4())

    SESSION_STORE[session_id] = session

    
    response = RedirectResponse(f"/assistant")
    response.set_cookie(
        key="session",
        value=session_id,
        httponly=True,
        secure=False, 
        samesite="lax",
        max_age=60 * 60,
    )

    return response    


async def verify_keycloak_jwt(
    token: str,
    *,
    access_token: str | None = None,
    verify_audience: bool = True,
) -> dict:
    issuer = f"{settings.KEYCLOAK_BASE_URL}/realms/{settings.REALM}"
    jwks_url = f"{issuer}/protocol/openid-connect/certs"

    async with httpx.AsyncClient() as client:
        jwks = (await client.get(jwks_url)).json()

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header["kid"]

        key = next(jwk for jwk in jwks["keys"] if jwk["kid"] == kid)

        decode_kwargs: dict = {
            "algorithms": ["RS256"],
            "issuer": issuer,
        }
        if verify_audience:
            decode_kwargs["audience"] = settings.CLIENT_ID
        else:
            decode_kwargs["options"] = {"verify_aud": False}

        if access_token is not None:
            decode_kwargs["access_token"] = access_token

        claims = jwt.decode(token, key, **decode_kwargs)

        if not verify_audience:
            authorized_party = claims.get("azp")
            if authorized_party is not None and authorized_party != settings.CLIENT_ID:
                raise JWTError("Invalid authorized party")

        return claims

    except (JWTError, StopIteration):
        raise HTTPException(status_code=401, detail="Invalid token")    