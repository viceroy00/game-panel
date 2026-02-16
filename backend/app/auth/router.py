from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.auth.schemas import (
    LoginRequest, LoginResponse, TOTPVerifyRequest, TokenResponse,
    UserCreate, UserUpdate, UserResponse, PasswordChange,
    TOTPSetupResponse, TOTPActivateRequest, TOTPActivateResponse,
    RecoveryLoginRequest,
    EmailVerifySendRequest, EmailVerifyConfirmRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    Recover2FASendRequest, Recover2FAConfirmRequest,
)
from app.auth.service import (
    verify_password, hash_password,
    create_access_token, create_temp_token, create_refresh_token, decode_token,
    generate_totp_secret, get_totp_uri, generate_qr_code_base64, verify_totp,
    generate_recovery_codes, verify_recovery_code,
    is_account_locked, MAX_FAILED_ATTEMPTS, LOCKOUT_MINUTES,
    generate_email_code, create_email_token,
)
from app.auth.deps import get_current_user, require_admin

router = APIRouter(prefix="/api/auth", tags=["인증"])


# ═══════════════════════════════════════════
# 로그인 플로우
# ═══════════════════════════════════════════
#
# [관리자가 계정 생성] → totp_setup_required=True
#
# [최초 로그인]
#   1) POST /login (ID/PW) → status="2fa_setup_required" + temp_token
#   2) POST /totp/setup (temp_token) → QR코드 + secret
#   3) POST /totp/activate (temp_token + TOTP코드)
#      → 2FA 활성화 + 복구코드 8개 표출 + access_token 발급
#
# [이후 로그인]
#   1) POST /login (ID/PW) → status="2fa_required" + temp_token
#   2) POST /verify-2fa (temp_token + TOTP코드) → access_token
#
# [복구 코드 로그인]
#   1) POST /login (ID/PW) → temp_token
#   2) POST /verify-recovery (temp_token + 복구코드) → access_token
#      (사용된 복구 코드는 소멸)
# ═══════════════════════════════════════════


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증 실패")

    if is_account_locked(user):
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="계정이 잠겼습니다. 잠시 후 다시 시도하세요")

    if not verify_password(req.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증 실패")

    # 로그인 성공 → 실패 카운트 초기화
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()

    # Case 1: 2FA 미설정 → 강제 설정 필요
    if user.totp_setup_required and not user.totp_enabled:
        temp_token = create_temp_token(user.id, purpose="2fa_setup")
        await db.commit()
        return LoginResponse(status="2fa_setup_required", temp_token=temp_token)

    # Case 2: 2FA 설정됨 → TOTP 코드 입력 필요
    if user.totp_enabled:
        temp_token = create_temp_token(user.id, purpose="2fa")
        await db.commit()
        return LoginResponse(status="2fa_required", temp_token=temp_token)

    # Case 3: 2FA 비활성 (이론상 도달하지 않음 — 모든 계정은 2FA 필수)
    access_token = create_access_token(user.id, user.is_admin)
    refresh_token = create_refresh_token(user.id)
    await db.commit()
    return LoginResponse(status="authenticated", access_token=access_token, refresh_token=refresh_token)


# ─── 2FA 설정: QR 코드 생성 ───

@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def setup_totp(temp_token: str, db: AsyncSession = Depends(get_db)):
    """최초 로그인 시 2FA QR 코드 발급"""
    payload = decode_token(temp_token)
    if payload is None or payload.get("purpose") != "2fa_setup":
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

    # TOTP 시크릿 생성 (아직 활성화는 안 함)
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, user.username)
    qr_b64 = generate_qr_code_base64(uri)

    user.totp_secret = secret
    await db.commit()

    return TOTPSetupResponse(secret=secret, qr_code_uri=uri, qr_code_base64=qr_b64)


# ─── 2FA 설정: 코드 검증 → 활성화 → 복구 코드 발급 ───

@router.post("/totp/activate", response_model=TOTPActivateResponse)
async def activate_totp(req: TOTPActivateRequest, db: AsyncSession = Depends(get_db)):
    """TOTP 코드 확인 후 2FA 활성화 + 복구 코드 표출"""
    payload = decode_token(req.temp_token)
    if payload is None or payload.get("purpose") != "2fa_setup":
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.totp_secret:
        raise HTTPException(status_code=401, detail="먼저 /totp/setup을 호출하세요")

    if not verify_totp(user.totp_secret, req.totp_code):
        raise HTTPException(status_code=400, detail="TOTP 코드가 올바르지 않습니다. 다시 시도하세요")

    # 복구 코드 생성
    plain_codes, hashed_codes = generate_recovery_codes()

    # 2FA 활성화
    user.totp_enabled = True
    user.totp_setup_required = False
    user.recovery_codes = hashed_codes
    await db.commit()

    # 이메일 미인증 → 이메일 인증 단계로
    if not user.email_verified:
        email_temp = create_temp_token(user.id, purpose="email_verify", expire_minutes=30)
        return TOTPActivateResponse(
            message="2차 인증이 활성화되었습니다. 아래 복구 코드를 안전한 곳에 보관하세요. 이 코드는 다시 볼 수 없습니다!",
            recovery_codes=plain_codes,
            access_token=email_temp,  # 프론트에서 email_verify 플로우 진입용
            refresh_token="",
            email_verify_required=True,
        )

    # 정식 토큰 발급
    access_token = create_access_token(user.id, user.is_admin)
    refresh_token = create_refresh_token(user.id)

    return TOTPActivateResponse(
        message="2차 인증이 활성화되었습니다. 아래 복구 코드를 안전한 곳에 보관하세요. 이 코드는 다시 볼 수 없습니다!",
        recovery_codes=plain_codes,
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ─── 일반 2FA 검증 (로그인 2단계) ───

@router.post("/verify-2fa", response_model=TokenResponse)
async def verify_2fa(req: TOTPVerifyRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(req.temp_token)
    if payload is None or payload.get("purpose") != "2fa":
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.totp_secret:
        raise HTTPException(status_code=401, detail="인증 실패")

    if not verify_totp(user.totp_secret, req.totp_code):
        raise HTTPException(status_code=401, detail="2FA 코드가 올바르지 않습니다")

    # 이메일 미인증 → 이메일 인증 단계
    if not user.email_verified:
        email_temp = create_temp_token(user.id, purpose="email_verify", expire_minutes=30)
        return TokenResponse(access_token=email_temp, refresh_token="", email_verify_required=True)

    access_token = create_access_token(user.id, user.is_admin)
    refresh_token = create_refresh_token(user.id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ─── 복구 코드 로그인 ───

@router.post("/verify-recovery", response_model=TokenResponse)
async def verify_recovery(req: RecoveryLoginRequest, db: AsyncSession = Depends(get_db)):
    """복구 코드로 2FA 인증 (코드는 1회용 — 사용 후 소멸)"""
    payload = decode_token(req.temp_token)
    if payload is None or payload.get("purpose") != "2fa":
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.recovery_codes:
        raise HTTPException(status_code=401, detail="인증 실패")

    valid, index = verify_recovery_code(req.recovery_code, user.recovery_codes)
    if not valid:
        raise HTTPException(status_code=401, detail="복구 코드가 올바르지 않습니다")

    # 사용된 복구 코드 제거
    codes = list(user.recovery_codes)
    codes.pop(index)
    user.recovery_codes = codes
    await db.commit()

    remaining = len(codes)

    # 이메일 미인증 → 이메일 인증 단계
    if not user.email_verified:
        email_temp = create_temp_token(user.id, purpose="email_verify", expire_minutes=30)
        return TokenResponse(access_token=email_temp, refresh_token="", email_verify_required=True)

    access_token = create_access_token(user.id, user.is_admin)
    refresh_token = create_refresh_token(user.id)

    # 남은 복구 코드가 2개 이하면 경고 (프론트에서 처리)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ─── 토큰 갱신 ───

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="비활성 계정")

    new_access = create_access_token(user.id, user.is_admin)
    new_refresh = create_refresh_token(user.id)
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


# ═══════════════════════════════════════════
# 이메일 인증
# ═══════════════════════════════════════════

@router.post("/verify-email/send")
async def send_email_verification(req: EmailVerifySendRequest, db: AsyncSession = Depends(get_db)):
    """이메일 인증 코드 발송 (2FA 완료 후 호출)"""
    payload = decode_token(req.temp_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

    code = generate_email_code()
    user.email = req.email
    user.email_verify_code = code
    user.email_verify_expires = datetime.utcnow() + timedelta(hours=24)
    await db.commit()

    try:
        from app.mail.service import send_verification_code
        await send_verification_code(req.email, user.username, code)
    except Exception as e:
        print(f"[MAIL ERROR] 인증 코드 발송 실패: {e}")
        raise HTTPException(status_code=500, detail="인증 메일 발송에 실패했습니다")

    return {"message": "인증 코드가 이메일로 발송되었습니다"}


@router.post("/verify-email/confirm")
async def confirm_email_verification(req: EmailVerifyConfirmRequest, db: AsyncSession = Depends(get_db)):
    """이메일 인증 코드 확인"""
    payload = decode_token(req.temp_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

    if not user.email_verify_code or not user.email_verify_expires:
        raise HTTPException(status_code=400, detail="인증 코드를 먼저 요청하세요")

    if datetime.utcnow() > user.email_verify_expires:
        raise HTTPException(status_code=400, detail="인증 코드가 만료되었습니다. 다시 요청하세요")

    if user.email_verify_code != req.code:
        raise HTTPException(status_code=400, detail="인증 코드가 올바르지 않습니다")

    user.email_verified = True
    user.email_verify_code = None
    user.email_verify_expires = None
    await db.commit()

    # 이메일 인증 완료 → 정식 토큰 발급
    access_token = create_access_token(user.id, user.is_admin)
    refresh_token = create_refresh_token(user.id)
    return {"message": "이메일 인증이 완료되었습니다", "access_token": access_token, "refresh_token": refresh_token}


# ═══════════════════════════════════════════
# 비밀번호 재설정
# ═══════════════════════════════════════════

@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """비밀번호 재설정 이메일 발송"""
    result = await db.execute(select(User).where(User.email == req.email, User.email_verified == True))
    user = result.scalar_one_or_none()

    # 사용자 존재 여부와 관계없이 동일 응답 (이메일 열거 방지)
    if user:
        token = create_email_token(user.id, purpose="password_reset", expire_minutes=60)
        try:
            from app.mail.service import send_password_reset
            await send_password_reset(user.email, user.username, token)
        except Exception as e:
            print(f"[MAIL ERROR] 비밀번호 재설정 메일 실패: {e}")

    return {"message": "이메일이 등록되어 있다면 재설정 링크가 발송됩니다"}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """비밀번호 재설정 실행"""
    payload = decode_token(req.token)
    if payload is None or payload.get("purpose") != "password_reset" or payload.get("type") != "email":
        raise HTTPException(status_code=400, detail="유효하지 않거나 만료된 링크입니다")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="유효하지 않은 링크입니다")

    user.password_hash = hash_password(req.new_password)
    user.failed_login_count = 0
    user.locked_until = None
    await db.commit()

    return {"message": "비밀번호가 재설정되었습니다. 새 비밀번호로 로그인하세요"}


# ═══════════════════════════════════════════
# 2FA 이메일 복구
# ═══════════════════════════════════════════

@router.post("/recover-2fa/send")
async def send_2fa_recovery(req: Recover2FASendRequest, db: AsyncSession = Depends(get_db)):
    """2FA 복구 코드를 인증된 이메일로 발송"""
    payload = decode_token(req.temp_token)
    if payload is None or payload.get("purpose") != "2fa":
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

    if not user.email or not user.email_verified:
        raise HTTPException(status_code=400, detail="인증된 이메일이 없습니다. 관리자에게 문의하세요")

    code = generate_email_code()
    user.email_verify_code = code  # 임시 코드 재활용
    user.email_verify_expires = datetime.utcnow() + timedelta(minutes=15)
    await db.commit()

    try:
        from app.mail.service import send_2fa_recovery_code
        await send_2fa_recovery_code(user.email, user.username, code)
    except Exception as e:
        print(f"[MAIL ERROR] 2FA 복구 메일 실패: {e}")
        raise HTTPException(status_code=500, detail="복구 메일 발송에 실패했습니다")

    # 이메일 마스킹
    email = user.email
    at_idx = email.index("@")
    masked = email[0:2] + "***" + email[at_idx:]
    return {"message": f"복구 코드가 {masked}(으)로 발송되었습니다"}


@router.post("/recover-2fa/confirm")
async def confirm_2fa_recovery(req: Recover2FAConfirmRequest, db: AsyncSession = Depends(get_db)):
    """2FA 복구 코드 확인 → 2FA 초기화 → 재설정 필요"""
    payload = decode_token(req.temp_token)
    if payload is None or payload.get("purpose") != "2fa":
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

    if not user.email_verify_code or not user.email_verify_expires:
        raise HTTPException(status_code=400, detail="복구 코드를 먼저 요청하세요")

    if datetime.utcnow() > user.email_verify_expires:
        raise HTTPException(status_code=400, detail="복구 코드가 만료되었습니다. 다시 요청하세요")

    if user.email_verify_code != req.code:
        raise HTTPException(status_code=400, detail="복구 코드가 올바르지 않습니다")

    # 2FA 초기화 → 다시 설정 필요
    user.totp_secret = None
    user.totp_enabled = False
    user.totp_setup_required = True
    user.recovery_codes = []
    user.email_verify_code = None
    user.email_verify_expires = None
    await db.commit()

    # 2FA 재설정 플로우로 진입
    temp_token = create_temp_token(user.id, purpose="2fa_setup")
    return {"message": "2FA가 초기화되었습니다. 다시 설정해주세요", "status": "2fa_setup_required", "temp_token": temp_token}


# ─── 내 정보 ───

@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id, username=user.username, display_name=user.display_name,
        email=user.email, email_verified=user.email_verified, is_admin=user.is_admin, is_active=user.is_active,
        totp_enabled=user.totp_enabled, totp_setup_required=user.totp_setup_required,
        created_at=user.created_at.isoformat(),
    )


# ─── 비밀번호 변경 ───

@router.post("/change-password")
async def change_password(
    req: PasswordChange,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(req.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다")

    user.password_hash = hash_password(req.new_password)
    await db.commit()
    return {"message": "비밀번호가 변경되었습니다"}


# ═══════════════════════════════════════════
# 유저 관리 (관리자)
# ═══════════════════════════════════════════

@router.post("/users", response_model=UserResponse)
async def create_user(
    req: UserCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="이미 존재하는 사용자명입니다")

    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
        email=req.email,
        is_admin=req.is_admin,
        totp_setup_required=True,  # 최초 로그인 시 2FA 설정 강제
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id, username=user.username, display_name=user.display_name,
        email=user.email, email_verified=user.email_verified, is_admin=user.is_admin, is_active=user.is_active,
        totp_enabled=user.totp_enabled, totp_setup_required=user.totp_setup_required,
        created_at=user.created_at.isoformat(),
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [
        UserResponse(
            id=u.id, username=u.username, display_name=u.display_name,
            email=u.email, email_verified=u.email_verified, is_admin=u.is_admin, is_active=u.is_active,
            totp_enabled=u.totp_enabled, totp_setup_required=u.totp_setup_required,
            created_at=u.created_at.isoformat(),
        )
        for u in users
    ]


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    req: UserUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id, username=user.username, display_name=user.display_name,
        email=user.email, email_verified=user.email_verified, is_admin=user.is_admin, is_active=user.is_active,
        totp_enabled=user.totp_enabled, totp_setup_required=user.totp_setup_required,
        created_at=user.created_at.isoformat(),
    )


# ─── 2FA 초기화 (관리자) ───

@router.post("/users/{user_id}/reset-2fa")
async def reset_2fa(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """관리자가 사용자의 2FA를 초기화 → 다음 로그인 시 재설정"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    user.totp_secret = None
    user.totp_enabled = False
    user.totp_setup_required = True
    user.recovery_codes = []
    await db.commit()

    return {"message": f"{user.username}의 2FA가 초기화되었습니다. 다음 로그인 시 재설정이 필요합니다"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="자기 자신은 삭제할 수 없습니다")

    await db.delete(user)
    await db.commit()
    return {"message": f"{user.username} 계정이 삭제되었습니다"}
