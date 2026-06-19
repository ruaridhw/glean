import json
import urllib.request
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from glean.config import Settings, get_settings
from glean.llm import LLMRouter

security = HTTPBearer(auto_error=False)


def get_llm_router(settings: Annotated[Settings, Depends(get_settings)]) -> LLMRouter:
    return LLMRouter.from_settings(settings)


@lru_cache(maxsize=1)
def _get_jwks(aws_region: str, user_pool_id: str) -> dict:
    url = f"https://cognito-idp.{aws_region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
        return json.loads(resp.read())


def verify_cognito_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )

    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        jwks = _get_jwks(settings.aws_region, settings.cognito_user_pool_id)
        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if key is None:
            _get_jwks.cache_clear()
            jwks = _get_jwks(settings.aws_region, settings.cognito_user_pool_id)
            key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown signing key",
            )

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.cognito_app_client_id,
            issuer=(f"https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.cognito_user_pool_id}"),
        )
        user_sub: str = payload["sub"]
        request.state.user_sub = user_sub
        return user_sub

    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
