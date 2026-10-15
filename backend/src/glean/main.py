from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastapi import FastAPI
from mangum import Mangum

from glean.catalogue.router import router as catalogue_router
from glean.dependencies import verify_cognito_token
from glean.dev.router import router as dev_router
from glean.health.router import router as health_router
from glean.meal_plan.router import router as meal_plan_router
from glean.observability import logger
from glean.receipts.router import router as receipts_router
from glean.recipes.router import router as recipes_router
from glean.shopping.router import router as shopping_router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
    logger.info("Glean API starting up")
    yield


app = FastAPI(title="Glean API", version="0.1.0", lifespan=lifespan)

app.include_router(health_router)
app.include_router(catalogue_router)
app.include_router(dev_router)
app.include_router(receipts_router)
app.include_router(recipes_router)
app.include_router(shopping_router)
app.include_router(meal_plan_router)

if os.environ.get("ENVIRONMENT") == "dev":
    app.dependency_overrides[verify_cognito_token] = lambda: "local-dev-user"
    logger.warning("Auth bypassed — ENVIRONMENT=dev")

handler = Mangum(app)
