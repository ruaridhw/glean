"""Per-user limit on the paid-model routes.

A route opts in with one line, `dependencies=[Depends(enforce_ai_rate_limit)]`. The limit is
`settings.rate_limit_per_hour` requests per hour for each Cognito sub.

A refused request answers 429 with the same body as always plus a `Retry-After` header holding the whole
seconds until the caller's window frees a slot, so the app can say "try again in N minutes" instead of
"later".

Storage is in-memory, so each warm Lambda container keeps its own counters: the limit is per container,
not global across the fleet.
"""

from __future__ import annotations

import math
import time
from typing import Annotated

from fastapi import Depends, HTTPException, status
from limits import RateLimitItem, parse
from slowapi import Limiter
from slowapi.util import get_remote_address

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token

limiter = Limiter(key_func=get_remote_address)


def charge_ai_request(user_sub: str, settings: Settings) -> None:
    """Count one paid-model request against the user's hourly allowance, or answer 429.

    The one implementation of the limit: a route that is only sometimes paid (the interview's first
    turn calls no model) charges through this rather than growing a limiter of its own.
    """
    allowance = parse(f"{settings.rate_limit_per_hour}/hour")
    if not limiter.limiter.hit(allowance, user_sub):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI request limit reached ({settings.rate_limit_per_hour} per hour). Try again later.",
            headers={"Retry-After": str(_seconds_until_a_slot_frees(allowance, user_sub))},
        )


def _seconds_until_a_slot_frees(allowance: RateLimitItem, user_sub: str) -> int:
    """Whole seconds until this caller's window resets, so the app can count down.

    `limits` gives the reset as a Unix timestamp. Ceiled and floored at one, because a `Retry-After` of
    `0` invites an immediate retry that is still refused, and the app's copy rounds up to whole minutes.
    """
    reset_time = limiter.limiter.get_window_stats(allowance, user_sub).reset_time
    return max(1, math.ceil(reset_time - time.time()))


def enforce_ai_rate_limit(
    user_sub: Annotated[str, Depends(verify_cognito_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    charge_ai_request(user_sub, settings)
