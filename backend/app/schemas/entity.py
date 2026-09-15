import uuid

from pydantic import BaseModel, ConfigDict, computed_field


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    name: str
    aliases: list[str]
    profile: dict | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def workload(self) -> int:
        active_items = (self.profile or {}).get("active_items", [])
        return len(active_items) if isinstance(active_items, list) else 0
