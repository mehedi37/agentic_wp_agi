import json
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.assistant import answer_question
from app.agents.assistant_memory import dialogue_graph
from app.api.deps import get_current_user
from app.db.session import get_session
from app.llm.factory import get_embedding_provider, get_llm_provider
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/assistant", tags=["assistant"],
                   dependencies=[Depends(get_current_user)])


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    thread_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    stream: bool = False


@router.post("/chat", response_model=None)
async def chat(payload: Question, session: Session = Depends(get_session),
               user: CurrentUser = Depends(get_current_user)) -> dict | StreamingResponse:
    graph = dialogue_graph(session)
    config = {"configurable": {"thread_id": f"assistant:{user.id}:{payload.thread_id}"}}
    history = graph.get_state(config).values.get("history", [])
    result = await answer_question(session, payload.question, get_llm_provider(),
                                   get_embedding_provider(), history=history)
    graph.invoke({"history": [*history, {"role": "user", "content": payload.question},
                              {"role": "assistant", "content": result["answer"]}]}, config)
    result["thread_id"] = str(payload.thread_id)
    session.commit()
    if payload.stream:
        def events() -> Iterator[str]:
            for start in range(0, len(result["answer"]), 80):
                yield "event: token\ndata: " + json.dumps({"text": result["answer"][start:start+80]}) + "\n\n"
            yield "event: done\ndata: " + json.dumps(result) + "\n\n"
        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    return result
