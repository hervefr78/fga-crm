# =============================================================================
# FGA CRM - GEO Routes : Prompts
# =============================================================================
"""Endpoints CRUD des prompts GEO rattaches a une marque."""

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.geo import GeoPrompt
from app.models.user import User
from app.schemas.geo import (
    GeoPromptCreate,
    GeoPromptResponse,
    GeoPromptUpdate,
)

from ._common import (
    _get_brand_or_404,
    _get_prompt_or_404,
    _parse_uuid,
    _require_geo_access,
    _require_geo_admin,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

@router.get("/brands/{brand_id}/prompts", response_model=list[GeoPromptResponse])
async def list_prompts(
    brand_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_access),
) -> list[GeoPromptResponse]:
    bid = _parse_uuid(brand_id, "brand_id")
    # Garde cross-FK : la marque parente doit appartenir a l'org du user
    await _get_brand_or_404(db, bid, user)
    prompts = (
        await db.execute(
            select(GeoPrompt)
            .where(and_(GeoPrompt.brand_id == bid, GeoPrompt.active.is_(True)))
            .order_by(GeoPrompt.created_at.desc())
            .limit(500)
        )
    ).scalars().all()
    return [GeoPromptResponse.model_validate(p) for p in prompts]


@router.post(
    "/brands/{brand_id}/prompts", response_model=GeoPromptResponse, status_code=201
)
async def create_prompt(
    brand_id: str,
    payload: GeoPromptCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_admin),
) -> GeoPromptResponse:
    bid = _parse_uuid(brand_id, "brand_id")
    # Garde cross-FK : la marque parente doit appartenir a l'org du user
    await _get_brand_or_404(db, bid, user)
    prompt = GeoPrompt(
        # Isolation multi-tenant : org resolue cote serveur, pas depuis le payload (DC18)
        organization_id=user.organization_id,
        brand_id=bid,
        text=payload.text,
        intent=payload.intent.value,
        persona=payload.persona,
        country=payload.country,
        language=payload.language,
        tags=payload.tags,
        priority=payload.priority,
        active=payload.active,
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return GeoPromptResponse.model_validate(prompt)


@router.put(
    "/brands/{brand_id}/prompts/{prompt_id}", response_model=GeoPromptResponse
)
async def update_prompt(
    brand_id: str,
    prompt_id: str,
    payload: GeoPromptUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_admin),
) -> GeoPromptResponse:
    bid = _parse_uuid(brand_id, "brand_id")
    pid = _parse_uuid(prompt_id, "prompt_id")
    prompt = await _get_prompt_or_404(db, bid, pid, user)

    data = payload.model_dump(exclude_unset=True)
    # intent est un enum -> stocker la valeur str
    if "intent" in data and data["intent"] is not None:
        data["intent"] = data["intent"].value
    for key, value in data.items():
        setattr(prompt, key, value)
    await db.commit()
    await db.refresh(prompt)
    return GeoPromptResponse.model_validate(prompt)


@router.delete("/brands/{brand_id}/prompts/{prompt_id}", status_code=204)
async def delete_prompt(
    brand_id: str,
    prompt_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_admin),
) -> None:
    bid = _parse_uuid(brand_id, "brand_id")
    pid = _parse_uuid(prompt_id, "prompt_id")
    prompt = await _get_prompt_or_404(db, bid, pid, user)
    prompt.active = False
    await db.commit()
