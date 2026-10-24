import asyncio

from sqlalchemy import select

from app.database import SessionLocal, engine
from app.models import User, UserRole
from app.security import hash_password


async def main() -> None:
    email = input("Admin email: ").strip().lower()
    full_name = input("Full name: ").strip()
    password = input("Password (min 8 chars, visible: local dev only): ").strip()

    if "@" not in email or not full_name or len(password) < 8:
        print("Invalid input. Nothing was changed.")
        return

    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user:
            user.role = UserRole.admin
            action = "promoted to admin"
        else:
            session.add(
                User(
                    email=email,
                    password_hash=await hash_password(password),
                    full_name=full_name,
                    role=UserRole.admin,
                )
            )
            action = "created as admin"
        await session.commit()

    await engine.dispose()
    print(f"{email} {action}.")


asyncio.run(main())