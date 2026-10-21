from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

from app.config import settings
from app.models import User

ALGORITHM = "RS256"

_PRIVATE_KEY = Path(settings.jwt_private_key_path).read_text()
_PUBLIC_KEY = Path(settings.jwt_public_key_path).read_text()


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.full_name,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, _PRIVATE_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        _PUBLIC_KEY,
        algorithms=[ALGORITHM],
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "sub", "iss"]},
    )