import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password: str, password_hash: str) -> bool:
    try:
        return await asyncio.to_thread(_hasher.verify, password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


_DUMMY_HASH = _hasher.hash("not-a-real-password")


async def burn_verify(password: str) -> None:
    """Spend the same time as a real check, so response timing doesn't reveal
    whether an email is registered."""
    await verify_password(password, _DUMMY_HASH)
    