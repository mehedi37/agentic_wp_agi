from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.assistant import answer_question
from app.api.deps import get_current_user
from app.db.session import get_session
from app.llm.factory import get_embedding_provider, get_llm_provider

router = APIRouter(prefix="/assistant", tags=["assistant"],
                   dependencies=[Depends(get_current_user)])


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


@router.post("/chat")
async def chat(payload: Question, session: Session = Depends(get_session)) -> dict:
    result = await answer_question(session, payload.question, get_llm_provider(),
                                   get_embedding_provider())
    session.commit()
    return result
