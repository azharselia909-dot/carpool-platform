from sqlalchemy import text

from app.database import engine


async def test_register_success(client, alice):
    response = await client.post("/auth/register", json=alice)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "driver"
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_lowercases_email_and_rejects_duplicates(client, alice):
    first = await client.post("/auth/register", json={**alice, "email": "Alice@Example.com"})
    assert first.status_code == 201
    assert first.json()["email"] == "alice@example.com"

    second = await client.post("/auth/register", json=alice)
    assert second.status_code == 409


async def test_register_validation(client, alice):
    short_password = await client.post("/auth/register", json={**alice, "password": "short"})
    assert short_password.status_code == 422

    self_made_admin = await client.post("/auth/register", json={**alice, "role": "admin"})
    assert self_made_admin.status_code == 422

    bad_email = await client.post("/auth/register", json={**alice, "email": "not-an-email"})
    assert bad_email.status_code == 422


async def test_password_is_stored_as_argon2_hash(client, registered_alice):
    async with engine.connect() as conn:
        stored = (await conn.execute(text("SELECT password_hash FROM users"))).scalar_one()

    assert stored.startswith("$argon2id$")
    assert registered_alice["password"] not in stored


async def test_login_sets_http_only_cookies(client, registered_alice):
    response = await client.post(
        "/auth/login",
        json={"email": registered_alice["email"], "password": registered_alice["password"]},
    )

    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 2
    for cookie in cookies:
        assert "httponly" in cookie.lower()
        assert "samesite=lax" in cookie.lower()
    assert any(c.startswith("access_token=") for c in cookies)
    assert any(c.startswith("refresh_token=") and "path=/auth" in c.lower() for c in cookies)


async def test_login_failures_look_identical(client, registered_alice):
    wrong_password = await client.post(
        "/auth/login",
        json={"email": registered_alice["email"], "password": "wrongpassword"},
    )
    unknown_email = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "wrongpassword"},
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    # Same message either way, so attackers can't discover which emails exist.
    assert wrong_password.json() == unknown_email.json()


async def test_me_requires_login(client, registered_alice):
    assert (await client.get("/auth/me")).status_code == 401

    await client.post(
        "/auth/login",
        json={"email": registered_alice["email"], "password": registered_alice["password"]},
    )
    me = await client.get("/auth/me")

    assert me.status_code == 200
    assert me.json()["email"] == registered_alice["email"]


async def test_logout_ends_the_session(client, registered_alice):
    await client.post(
        "/auth/login",
        json={"email": registered_alice["email"], "password": registered_alice["password"]},
    )
    assert (await client.get("/auth/me")).status_code == 200

    await client.post("/auth/logout")

    assert (await client.get("/auth/me")).status_code == 401


async def test_login_is_rate_limited_per_ip(client, registered_alice):
    attempt = {"email": registered_alice["email"], "password": "wrongpassword"}

    codes = [(await client.post("/auth/login", json=attempt)).status_code for _ in range(5)]
    assert codes == [401, 401, 401, 401, 401]

    blocked = await client.post("/auth/login", json=attempt)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1