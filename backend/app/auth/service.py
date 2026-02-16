import io
import base64
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
import qrcode
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User
from app.db.session import async_session

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── 패스워드 ───

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ─── JWT ───

def create_access_token(user_id: str, is_admin: bool, two_fa_verified: bool = True) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "is_admin": is_admin,
        "2fa_verified": two_fa_verified,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_temp_token(user_id: str, purpose: str = "2fa", expire_minutes: int = 5) -> str:
    """임시 토큰 (2FA 검증, 이메일 인증 등)"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": user_id,
        "2fa_verified": False,
        "purpose": purpose,  # "2fa" 또는 "2fa_setup"
        "exp": expire,
        "type": "temp",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


# ─── TOTP 2FA ───

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=settings.app_name)


def generate_qr_code_base64(uri: str) -> str:
    img = qrcode.make(uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# ─── 복구 코드 ───

RECOVERY_CODE_COUNT = 8


def generate_recovery_codes() -> tuple[list[str], list[str]]:
    """
    복구 코드 생성
    Returns: (평문 코드 리스트, 해시된 코드 리스트)
    평문은 사용자에게 한 번만 보여주고, 해시만 DB에 저장
    """
    plain_codes = []
    hashed_codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        code = secrets.token_hex(4).upper()  # 8자리 hex (예: A1B2C3D4)
        plain_codes.append(code)
        hashed_codes.append(hash_recovery_code(code))
    return plain_codes, hashed_codes


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.upper().encode()).hexdigest()


def verify_recovery_code(code: str, hashed_codes: list[str]) -> tuple[bool, int]:
    """
    복구 코드 검증
    Returns: (성공 여부, 사용된 코드 인덱스)
    """
    code_hash = hash_recovery_code(code)
    for i, stored_hash in enumerate(hashed_codes):
        if stored_hash == code_hash:
            return True, i
    return False, -1


# ─── 이메일 인증 코드 ───

def generate_email_code() -> str:
    """6자리 숫자 인증 코드"""
    import random
    return str(random.randint(100000, 999999))


def create_email_token(user_id: str, purpose: str, expire_minutes: int = 60) -> str:
    """이메일 링크용 JWT (비밀번호 재설정, 2FA 복구 등)"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": user_id,
        "purpose": purpose,
        "exp": expire,
        "type": "email",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ─── 계정 잠금 ───

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def is_account_locked(user: User) -> bool:
    if user.locked_until and user.locked_until > datetime.utcnow():
        return True
    return False


# ─── 초기 관리자 생성 ───

async def create_initial_admin():
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == settings.admin_username))
        existing = result.scalar_one_or_none()

        if existing is None:
            admin = User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                display_name="관리자",
                email=settings.admin_email,
                email_verified=True,  # 관리자는 이메일 인증 면제
                is_admin=True,
                is_active=True,
                totp_setup_required=True,
            )
            session.add(admin)
            await session.commit()
            print(f"[INIT] 관리자 계정 생성됨: {settings.admin_username}")
        else:
            print(f"[INIT] 관리자 계정 이미 존재: {settings.admin_username}")
