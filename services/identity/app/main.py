from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.routes import admin, auth

app = FastAPI(title="Identity Service")

app.include_router(auth.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {"service": "identity", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(session: AsyncSession = Depends(get_session)):
    result = await session.execute(text("SELECT current_database(), current_user"))
    database, user = result.one()
    return {"database": database, "user": user}