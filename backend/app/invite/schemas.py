from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class InviteCodeCreate(BaseModel):
    max_uses: int = Field(default=1, ge=1, le=10)
    note: Optional[str] = Field(default=None, max_length=200)
    expires_hours: Optional[int] = Field(default=72, ge=1, le=720)  # 최대 30일


class InviteCodeResponse(BaseModel):
    id: str
    code: str
    max_uses: int
    use_count: int
    is_active: bool
    note: Optional[str]
    expires_at: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class InviteRegisterRequest(BaseModel):
    """초대 코드로 가입"""
    invite_code: str = Field(min_length=8, max_length=20)
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    display_name: Optional[str] = None
    email: Optional[str] = None
