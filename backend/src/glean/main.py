from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from mangum import Mangum
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from glean.dev.router import router as dev_router
from glean.health.router import router as health_router
from glean.observability import logger
from glean.receipts.router import router as receipts_router
from glean.recipes.router import router as recipes_router


def get_user_sub(request: Request) -> str:
    return getattr(request.state, "user_sub", get_remote_address(request))


limiter = Limiter(key_func=get_user_sub)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
    logger.info("Glean API starting up")
    yield


app = FastAPI(title="Glean API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(health_router)
app.include_router(dev_router)
app.include_router(receipts_router)
app.include_router(recipes_router)

handler = Mangum(app)
