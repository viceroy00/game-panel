from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User, Permission
from app.auth.deps import require_discord_role


class RequirePermission:
    """컨테이너별 액션 권한 검증 디펜던시 (Discord 역할 + RBAC 이중 체크)"""

    def __init__(self, action: str):
        self.action = action

    async def __call__(
        self,
        container_name: str,
        user: User = Depends(require_discord_role),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # 관리자는 전체 권한
        if user.is_admin:
            return user

        result = await db.execute(
            select(Permission).where(
                Permission.user_id == user.id,
                Permission.container_name == container_name,
            )
        )
        perm = result.scalar_one_or_none()

        if perm is None or self.action not in perm.actions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"'{container_name}'에 대한 '{self.action}' 권한이 없습니다",
            )
        return user
