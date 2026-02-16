from pydantic import BaseModel
from typing import Optional


class PermissionCreate(BaseModel):
    user_id: str
    container_name: str
    actions: list[str]  # ["start", "stop", "restart", "logs", "rcon", "config", "backup"]


class PermissionUpdate(BaseModel):
    actions: list[str]


class PermissionResponse(BaseModel):
    id: str
    user_id: str
    username: Optional[str] = None
    container_name: str
    actions: list[str]
    granted_at: str

    class Config:
        from_attributes = True


VALID_ACTIONS = {"start", "stop", "restart", "logs", "rcon", "config", "backup", "delete", "files"}
