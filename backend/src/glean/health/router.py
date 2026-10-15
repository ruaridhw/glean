from typing import Annotated

from fastapi import APIRouter, Depends

from glean.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {"status": "ok", "commit": settings.git_sha}
