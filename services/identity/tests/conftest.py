import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Point the app at TEST resources BEFORE any app module is imported.
# (Settings are read at import time, and real environment variables beat .env.)
# ---------------------------------------------------------------------------
_dev_url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env").get("DATABASE_URL")
if not _dev_url:
    raise RuntimeError("DATABASE_URL not found in the environment or services/identity/.env")

os.environ["DATABASE_URL"] = _dev_url.rsplit("/", 1)[0] + "/identity_test_db"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"  # Redis database 1, not your dev one
os.chdir(ROOT)  # the app reads keys/private.pem relative to this folder

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.redis_client import redis_client  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def prepare_test_environment():
    # Safety guards: never let a test wipe the dev database or dev Redis.
    assert engine.url.database.endswith("_test_db"), "Refusing to run on a non-test database"
    assert redis_client.connection_pool.connection_kwargs.get("db") == 1, "Refusing to flush a non-test Redis"

    # Build the schema by running the real Alembic migrations, which also tests them.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        check=True,
    )


@pytest_asyncio.fixture(autouse=True)
async def clean_state():
    """Every test starts with empty tables and empty rate-limit counters."""
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE refresh_tokens, users CASCADE"))
    await redis_client.flushdb()
    yield


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def alice():
    return {
        "email": "alice@example.com",
        "password": "supersecret123",
        "full_name": "Alice Sharma",
        "role": "driver",
    }


@pytest_asyncio.fixture
async def registered_alice(client, alice):
    response = await client.post("/auth/register", json=alice)
    assert response.status_code == 201
    return alice