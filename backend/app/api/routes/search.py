import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.llm.factory import get_embedding_provider
from app.memory.retrieval import SearchResult, hybrid_search
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SearchResult])
async def search(
    q: str,
    k: int = 10,
    chat_id: uuid.UUID | None = None,
    _user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[SearchResult]:
    provider = get_embedding_provider()
    return await hybrid_search(session, q, provider, k=k, chat_id=chat_id)
