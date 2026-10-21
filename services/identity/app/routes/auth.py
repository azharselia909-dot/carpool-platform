from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.deps import get_current_user
from app.models import User, UserRole
from app.schemas import LoginRequest, RegisterRequest, UserOut
from app.security import burn_verify, hash_password, verify_password
from app.tokens import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "access_token"


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

    token = create_access_token(user)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.access_token_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return user


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return {"detail": "Logged out"}