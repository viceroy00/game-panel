from pydantic import BaseModel
from typing import Optional


class GameRequestCreate(BaseModel):
    game_name: str
    player_count: int = 1
    preferred_time: Optional[str] = None
    notes: Optional[str] = None


class GameRequestResponse(BaseModel):
    id: str
    requester_id: Optional[str] = None
    requester_name: str
    requester_email: Optional[str] = None
    game_name: str
    player_count: int
    preferred_time: Optional[str]
    notes: Optional[str]
    config_file_path: Optional[str] = None
    status: str
    status_label: str = ""
    admin_notes: Optional[str]
    server_address: Optional[str] = None
    server_port: Optional[str] = None
    server_password: Optional[str] = None
    config_path: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class GameRequestReview(BaseModel):
    status: str
    admin_notes: Optional[str] = None
    server_address: Optional[str] = None
    server_port: Optional[str] = None
    server_password: Optional[str] = None
    config_path: Optional[str] = None
