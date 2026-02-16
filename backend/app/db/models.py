import uuid
import secrets
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, JSON, Text, Integer
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    email_verified = Column(Boolean, default=False)
    email_verify_code = Column(String(6), nullable=True)
    email_verify_expires = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Discord 연동
    discord_id = Column(String(20), unique=True, nullable=True, index=True)
    discord_username = Column(String(100), nullable=True)
    discord_avatar = Column(String(255), nullable=True)
    discord_roles = Column(JSON, default=list)  # Discord 서버 역할 ID 목록

    # 2FA — 최초 로그인 시 강제 설정
    totp_secret = Column(String(32), nullable=True)
    totp_enabled = Column(Boolean, default=False)
    totp_setup_required = Column(Boolean, default=True)
    recovery_codes = Column(JSON, default=list)

    # 가입 경로
    registered_via = Column(String(20), default="admin")  # admin, discord, invite

    # Security
    failed_login_count = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    permissions = relationship("Permission", back_populates="user", cascade="all, delete-orphan", foreign_keys="[Permission.user_id]")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    container_name = Column(String(100), nullable=False)
    actions = Column(JSON, default=list)   # ["start","stop","restart","logs","files"]

    granted_by = Column(String, ForeignKey("users.id"), nullable=True)
    granted_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="permissions", foreign_keys=[user_id])


class GameConfigTemplate(Base):
    """관리자가 업로드하는 게임별 설정 양식"""
    __tablename__ = "game_config_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    game_name = Column(String(100), unique=True, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# 신청 상태 단계:
# pending → approved → building → ready → permission_granted → firewall_done → onboarded
# pending → rejected
REQUEST_STAGES = [
    "pending", "approved", "building", "ready",
    "permission_granted", "firewall_done", "onboarded", "rejected",
]

REQUEST_STAGE_LABELS = {
    "pending": "대기",
    "approved": "승인",
    "building": "서버 생성중",
    "ready": "생성 완료",
    "permission_granted": "권한 부여 완료",
    "firewall_done": "방화벽 설정 완료",
    "onboarded": "온보딩 완료",
    "rejected": "거절",
}


class GameRequest(Base):
    __tablename__ = "game_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    requester_id = Column(String, ForeignKey("users.id"), nullable=True)  # v0.4.0 레거시 호환
    game_name = Column(String(100), nullable=False)
    player_count = Column(Integer, default=1)
    preferred_time = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    config_file_path = Column(String(500), nullable=True)  # 사용자 업로드 설정 파일

    status = Column(String(30), default="pending")
    admin_notes = Column(Text, nullable=True)
    server_address = Column(String(255), nullable=True)
    server_port = Column(String(20), nullable=True)
    server_password = Column(String(100), nullable=True)
    config_path = Column(String(500), nullable=True)
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class ContainerState(Base):
    """게임 컨테이너 상태 추적 — 헬스체크 + 자동 삭제용"""
    __tablename__ = "container_states"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    container_name = Column(String(100), unique=True, nullable=False, index=True)
    container_id = Column(String(64), nullable=True)
    game_name = Column(String(100), nullable=True)

    last_status = Column(String(20), default="unknown")
    last_checked_at = Column(DateTime, nullable=True)
    stopped_since = Column(DateTime, nullable=True)
    delete_warning_sent = Column(Boolean, default=False)
    down_alert_sent = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InviteCode(Base):
    """초대 코드 — 디스코드 안 쓰는 지인용"""
    __tablename__ = "invite_codes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(16), unique=True, nullable=False, index=True,
                  default=lambda: secrets.token_urlsafe(12)[:16].upper())
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    used_by = Column(String, ForeignKey("users.id"), nullable=True)
    max_uses = Column(Integer, default=1)
    use_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    note = Column(String(200), nullable=True)  # "김OO한테 줄 코드"

    created_at = Column(DateTime, default=datetime.utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
