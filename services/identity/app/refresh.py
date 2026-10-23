import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import RefreshToken


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue_refresh_token(
    session: AsyncSession,
    user_id: uuid.UUID,
    family_id: uuid.UUID | None = None,
) -> str:
    """Create a refresh token row and return the RAW token (shown to the client once).
    The caller is responsible for committing the session."""
    raw = secrets.token_urlsafe(48)
    session.add(
        RefreshToken(
            user_id=user_id,
            family_id=family_id or uuid.uuid4(),
            token_hash=hash_refresh_token(raw),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.refresh_token_days),
        )
    )
    return raw


async def revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    """Revoke every still-active token in a family. Caller commits."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )