import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Item, ItemHistory
from app.db.session import get_session
from app.schemas.auth import CurrentUser
from app.schemas.item import ItemOut

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[ItemOut])
def list_items(
    item_type: str | None = None,
    item_status: str | None = None,
    chat_id: uuid.UUID | None = None,
    owner_participant_id: uuid.UUID | None = None,
    overdue: bool = False,
    _user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Item]:
    query = select(Item).order_by(Item.created_at.desc())
    if item_type is not None:
        query = query.where(Item.type == item_type)
    if item_status is not None:
        query = query.where(Item.status == item_status)
    if chat_id is not None:
        query = query.where(Item.chat_id == chat_id)
    if owner_participant_id is not None:
        query = query.where(Item.owner_participant_id == owner_participant_id)
    if overdue:
        now = datetime.now(tz=timezone.utc)
        query = query.where(
            Item.due_at.is_not(None), Item.due_at < now, Item.status.notin_(["done", "cancelled"])
        )
    return list(session.scalars(query))


@router.patch("/{item_id}/status", response_model=ItemOut)
def update_item_status(
    item_id: uuid.UUID,
    new_status: str = Body(..., embed=True),
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Item:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    old_status = item.status
    item.status = new_status
    session.add(
        ItemHistory(
            item_id=item.id,
            change={"field": "status", "from": old_status, "to": new_status},
            actor="user",
        )
    )
    session.commit()
    return item
