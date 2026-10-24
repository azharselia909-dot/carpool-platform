import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.deps import require_roles
from app.models import RefreshToken, User, UserRole
from app.schemas import AdminUserUpdate, UserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_roles(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
):
    result = await session.scalars(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    return result.all()


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    admin: User = Depends(require_roles(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    changes = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }

    if user.id == admin.id and (
        changes.get("is_active") is False
        or ("role" in changes and changes["role"] != UserRole.admin)
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Admins cannot deactivate or demote themselves",
        )

    for field, value in changes.items():
        setattr(user, field, value)

    # A deactivated user must not be able to refresh their way back in.
    if changes.get("is_active") is False:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )

    await session.commit()
    await session.refresh(user)
    return user