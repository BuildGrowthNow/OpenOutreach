"""Links Router - Phase 6 deferred feature.

Link tracking is a secondary surface (post-launch feature).
Users should track engagement via UTM parameters and direct analytics.
This router is stubbed to fail loudly if somehow called in production.
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["Links"])


@router.get("")
async def list_links():
    raise HTTPException(
        status_code=501,
        detail="Link tracking is not available in this phase. Planned for post-launch."
    )


@router.post("")
async def create_link():
    raise HTTPException(
        status_code=501,
        detail="Link tracking is not available in this phase. Planned for post-launch."
    )


@router.get("/{link_id}")
async def get_link(link_id: str):  # noqa: ARG001
    raise HTTPException(
        status_code=501,
        detail="Link tracking is not available in this phase. Planned for post-launch."
    )


@router.patch("/{link_id}")
async def update_link(link_id: str):  # noqa: ARG001
    raise HTTPException(
        status_code=501,
        detail="Link tracking is not available in this phase. Planned for post-launch."
    )


@router.delete("/{link_id}")
async def delete_link(link_id: str):  # noqa: ARG001
    raise HTTPException(
        status_code=501,
        detail="Link tracking is not available in this phase. Planned for post-launch."
    )
