import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Entity
from app.db.session import get_session
from app.schemas.auth import CurrentUser
from app.schemas.entity import EntityOut

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("", response_model=list[EntityOut])
def list_entities(
    kind: str | None = None,
    _user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Entity]:
    query = select(Entity).order_by(Entity.name)
    if kind is not None:
        query = query.where(Entity.kind == kind)
    return list(session.scalars(query))


@router.get("/{entity_id}", response_model=EntityOut)
def get_entity(
    entity_id: uuid.UUID,
    _user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Entity:
    entity = session.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    return entity
