from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.deps import get_current_user
from app.models import RefreshToken, User, UserRole
from app.refresh import hash_refresh_token, issue_refresh_token, revoke_family
from app.schemas import LoginRequest, RegisterRequest, UserOut
from app.security import burn_verify, hash_password, verify_password
from app.tokens import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/auth"  # the browser only sends it to /auth/* endpoints


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        max_age=settings.access_token_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key=ACCESS_COOKIE,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    email = payload.email.lower()

    existing = await session.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=email,
        password_hash=await hash_password(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=UserRole(payload.role),
    )
    session.add(user)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    await session.refresh(user)
    return user


@router.post("/login", response_model=UserOut)
async def login(
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    user = await session.scalar(select(User).where(User.email == payload.email.lower()))

    if user is None:
        await burn_verify(payload.password)
        raise invalid

    if not await verify_password(payload.password, user.password_hash) or not user.is_active:
        raise invalid

    access_token = create_access_token(user)
    refresh_token = await issue_refresh_token(session, user.id)  # starts a new family
    await session.commit()

    _set_auth_cookies(response, access_token, refresh_token)
    return user


@router.post("/refresh", response_model=UserOut)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
):
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    if refresh_token is None:
        raise invalid

    row = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(refresh_token)
        )
    )
    if row is None:
        raise invalid

    # An already-used token is being presented again: probable theft.
    # Revoke the whole family so BOTH the thief and the real user must log in again.
    if row.revoked_at is not None:
        await revoke_family(session, row.family_id)
        await session.commit()
        raise invalid

    if row.expires_at <= datetime.now(timezone.utc):
        raise invalid

    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise invalid

    # Atomically claim this token. If two requests race with the same token,
    # only one UPDATE matches revoked_at IS NULL; the loser is treated as reuse.
    claimed = await session.execute(
        update(RefreshToken)
        .where(RefreshToken.id == row.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=func.now())
        .returning(RefreshToken.id)
    )
    if claimed.scalar_one_or_none() is None:
        await revoke_family(session, row.family_id)
        await session.commit()
        raise invalid

    new_refresh = await issue_refresh_token(session, user.id, family_id=row.family_id)
    new_access = create_access_token(user)
    await session.commit()

    _set_auth_cookies(response, new_access, new_refresh)
    return user


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
):
    if refresh_token:
        row = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(refresh_token)
            )
        )
        if row:
            await revoke_family(session, row.family_id)
            await session.commit()

    _clear_auth_cookies(response)
    return {"detail": "Logged out"}