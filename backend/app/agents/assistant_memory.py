"""Bounded assistant dialogue persisted in the user's checkpoint namespace."""
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.checkpoints import session_checkpointer
from app.llm.base import ChatMessage


class DialogueState(TypedDict):
    history: list[ChatMessage]


def dialogue_graph(session: Session) -> Any:
    def remember(state: DialogueState) -> dict:
        return {"history": state["history"][-40:]}

    graph = StateGraph(DialogueState)
    graph.add_node("remember", remember)
    graph.set_entry_point("remember")
    graph.add_edge("remember", END)
    return graph.compile(checkpointer=session_checkpointer(session))
