"""Per-user limit on the paid-model routes.

A route opts in with one line, `dependencies=[Depends(enforce_ai_rate_limit)]`. The limit is
`settings.rate_limit_per_hour` requests per hour for each Cognito sub.

Storage is in-memory, so each warm Lambda container keeps its own counters: the limit is per
container, not global across the fleet.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from limits import parse
from slowapi import Limiter
from slowapi.util import get_remote_address

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token

limiter = Limiter(key_func=get_remote_address)


def enforce_ai_rate_limit(
    user_sub: Annotated[str, Depends(verify_cognito_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    allowance = parse(f"{settings.rate_limit_per_hour}/hour")
    if not limiter.limiter.hit(allowance, user_sub):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI request limit reached ({settings.rate_limit_per_hour} per hour). Try again later.",
        )
