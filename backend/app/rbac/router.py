from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User, Permission
from app.auth.deps import require_admin
from app.rbac.schemas import PermissionCreate, PermissionUpdate, PermissionResponse, VALID_ACTIONS
from app.discord.notify import notify_permission_granted
from app.mail.service import send_permission_granted

router = APIRouter(prefix="/api/permissions", tags=["권한 관리"])


@router.post("/", response_model=PermissionResponse)
async def grant_permission(
    req: PermissionCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # 유효한 액션인지 검증
    invalid = set(req.actions) - VALID_ACTIONS
    if invalid:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 액션: {invalid}")

    # 대상 유저 확인
    result = await db.execute(select(User).where(User.id == req.user_id))
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    # 기존 권한 확인
    result = await db.execute(
        select(Permission).where(
            Permission.user_id == req.user_id,
            Permission.container_name == req.container_name,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.actions = req.actions
        await db.commit()
        await db.refresh(existing)

        # 알림 발송
        try:
            await notify_permission_granted(target_user.username, req.container_name, req.actions, is_new=False)
        except Exception:
            pass
        if target_user.email:
            try:
                await send_permission_granted(target_user.email, target_user.display_name or target_user.username, req.container_name, req.actions, is_new=False)
            except Exception:
                pass

        return PermissionResponse(
            id=existing.id, user_id=existing.user_id, username=target_user.username,
            container_name=existing.container_name, actions=existing.actions,
            granted_at=existing.granted_at.isoformat(),
        )

    perm = Permission(
        user_id=req.user_id,
        container_name=req.container_name,
        actions=req.actions,
        granted_by=admin.id,
    )
    db.add(perm)
    await db.commit()
    await db.refresh(perm)

    # 알림 발송
    try:
        await notify_permission_granted(target_user.username, req.container_name, req.actions, is_new=True)
    except Exception:
        pass
    if target_user.email:
        try:
            await send_permission_granted(target_user.email, target_user.display_name or target_user.username, req.container_name, req.actions, is_new=True)
        except Exception:
            pass

    return PermissionResponse(
        id=perm.id, user_id=perm.user_id, username=target_user.username,
        container_name=perm.container_name, actions=perm.actions,
        granted_at=perm.granted_at.isoformat(),
    )


@router.get("/", response_model=list[PermissionResponse])
async def list_permissions(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Permission, User.username)
        .join(User, Permission.user_id == User.id)
        .order_by(Permission.container_name)
    )
    rows = result.all()
    return [
        PermissionResponse(
            id=p.id, user_id=p.user_id, username=username,
            container_name=p.container_name, actions=p.actions,
            granted_at=p.granted_at.isoformat(),
        )
        for p, username in rows
    ]


@router.get("/user/{user_id}", response_model=list[PermissionResponse])
async def get_user_permissions(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Permission).where(Permission.user_id == user_id)
    )
    perms = result.scalars().all()
    return [
        PermissionResponse(
            id=p.id, user_id=p.user_id,
            container_name=p.container_name, actions=p.actions,
            granted_at=p.granted_at.isoformat(),
        )
        for p in perms
    ]


@router.delete("/{permission_id}")
async def revoke_permission(
    permission_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    perm = result.scalar_one_or_none()
    if perm is None:
        raise HTTPException(status_code=404, detail="권한을 찾을 수 없습니다")

    await db.delete(perm)
    await db.commit()
    return {"message": "권한이 삭제되었습니다"}
