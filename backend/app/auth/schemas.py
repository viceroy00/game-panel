from pydantic import BaseModel, Field
from typing import Optional


# ─── 로그인 ───
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    """로그인 결과 — 상황에 따라 다른 필드 반환"""
    status: str  # "2fa_required" | "2fa_setup_required" | "authenticated"
    temp_token: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class TOTPVerifyRequest(BaseModel):
    temp_token: str
    totp_code: str = Field(min_length=6, max_length=8)  # 6자리 TOTP 또는 8자리 복구코드


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    email_verify_required: bool = False


# ─── 2FA 설정 (최초 등록) ───
class TOTPSetupResponse(BaseModel):
    secret: str
    qr_code_uri: str
    qr_code_base64: str


class TOTPActivateRequest(BaseModel):
    """QR 스캔 후 코드 입력하여 2FA 활성화"""
    temp_token: str
    totp_code: str = Field(min_length=6, max_length=6)


class TOTPActivateResponse(BaseModel):
    """활성화 성공 → 복구 코드 표출"""
    message: str
    recovery_codes: list[str]  # 평문 복구 코드 (이 시점에만 보여줌)
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    email_verify_required: bool = False


# ─── 유저 관리 ───
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    display_name: Optional[str] = None
    email: Optional[str] = None
    is_admin: bool = False


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: Optional[str]
    email: Optional[str]
    email_verified: bool = False
    is_admin: bool
    is_active: bool
    totp_enabled: bool
    totp_setup_required: bool
    created_at: str

    class Config:
        from_attributes = True


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


# ─── 복구 코드로 로그인 ───
class RecoveryLoginRequest(BaseModel):
    temp_token: str
    recovery_code: str = Field(min_length=8, max_length=8)


# ─── 이메일 인증 ───
class EmailVerifySendRequest(BaseModel):
    temp_token: str
    email: str

class EmailVerifyConfirmRequest(BaseModel):
    temp_token: str
    code: str = Field(min_length=6, max_length=6)


# ─── 비밀번호 재설정 ───
class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


# ─── 2FA 이메일 복구 ───
class Recover2FASendRequest(BaseModel):
    temp_token: str

class Recover2FAConfirmRequest(BaseModel):
    temp_token: str
    code: str = Field(min_length=6, max_length=6)
