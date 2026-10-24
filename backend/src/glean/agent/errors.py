"""The typed failures a run can end with. The codes are the app's error catalogue (spec §6.3)."""

from __future__ import annotations

from glean.sessions.models import SessionError, SessionErrorCode


class AgentError(Exception):
    """A run stopped for a reason the household can be told about."""

    def __init__(self, error: SessionError) -> None:
        super().__init__(error.code.value)
        self.error = error


class SessionCancelled(Exception):
    """The household cancelled while the run was between steps.

    A control-flow signal, not a failure: the record is already `cancelled` and the run must write
    nothing more -- no progress line, no result, no error (spec §6.3).
    """


def model_error_for(exception: Exception) -> SessionError:
    """The session error a failed model call becomes.

    A provider 429 is `rate_limited`, carrying the wait it asked for in whole minutes; anything else
    the model did is `model_error`. Classified from the exception's shape, so no provider SDK is
    imported here and a new model client needs no change to this module.
    """
    response = getattr(exception, "response", None)
    status = getattr(exception, "status_code", None) or getattr(response, "status_code", None)
    if status != 429:
        return SessionError(code=SessionErrorCode.MODEL_ERROR)
    headers = getattr(response, "headers", None) or {}
    retry_after = headers.get("retry-after") or headers.get("Retry-After")
    try:
        seconds = int(str(retry_after))
    except (TypeError, ValueError):
        return SessionError(code=SessionErrorCode.RATE_LIMITED)
    return SessionError(code=SessionErrorCode.RATE_LIMITED, retry_after_minutes=max(1, -(-seconds // 60)))


def budget_spent() -> SessionError:
    """The 90 s budget ran out before the plan was finished.

    The spec's degraded fallback (the scorer's best plan with template reasons) needs the scorer, which
    V6 adds; until then the honest outcome is the retryable model error rather than a half-made week.
    """
    return SessionError(code=SessionErrorCode.MODEL_ERROR)
