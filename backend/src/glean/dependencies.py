from fastapi import Request


def verify_cognito_token(request: Request) -> str:
    """Stub — overridden in tests via dependency_overrides."""
    raise NotImplementedError("JWT verification not yet configured")
