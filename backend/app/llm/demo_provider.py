"""Conservative, deterministic demo extraction; not a substitute for a language model."""
import re

from app.llm.base import BaseModelT, ChatMessage
from app.llm.fake_provider import FakeProvider


class DemoProvider(FakeProvider):
    async def structured(self, messages: list[ChatMessage], *, response_model: type[BaseModelT],
                         system: str | None = None, model: str | None = None) -> BaseModelT:
        if response_model.__name__ == "_JudgeOutput":
            return response_model.model_validate({"confidence": 0.65})
        if response_model.__name__ != "AnalystOutput":
            return await super().structured(messages, response_model=response_model,
                                            system=system, model=model)
        transcript = self._last_user_text(messages)
        items = []
        for mid, body in re.findall(r"\[([0-9a-f-]{36})\] [^\n]+? - ([^\n]+)", transcript):
            lowered = body.lower()
            kind = next((kind for kind, terms in (
                ("decision", ("decided", "approved", "decision:", "সিদ্ধান্ত")),
                ("risk", ("risk", "ঝুঁকি")),
                ("issue", ("blocked", "broken", "incident", "সমস্যা")),
                ("action", ("will ", "please ", "need to", "করতে হবে")),
            ) if any(term in lowered for term in terms)), None)
            if kind:
                items.append({"type": kind, "title": body[:180], "confidence": 0.55,
                              "evidence": [{"message_id": mid, "quote": body}]})
        return response_model.model_validate({"topic": "Demo extraction", "category": "general",
            "sentiment": "neutral", "urgency": "normal", "items": items})
