# Carpool Platform

A BlaBlaCar-style carpooling platform, built step by step as a hands-on project to learn
**microservices, secure authentication, PostGIS geospatial search, concurrency-safe seat booking,
WebSockets, and an AI booking agent**.

> **Status: Phase 1 of 8 complete.** The Identity service (authentication and authorization) is
> built and tested. The other services are designed but not yet implemented. This README is
> explicit about which is which.

## What is built vs planned

| Part | Status | What it does |
|---|---|---|
| Local infrastructure | Built | Postgres + PostGIS and Redis via Docker Compose |
| Identity service | Built | Registration, login, refresh tokens, roles, admin endpoints, rate limiting |
| Automated tests (Identity) | Built | 9 integration tests against real Postgres and Redis |
| Ride service | Planned | Publish rides with stops, PostGIS route search, seat inventory |
| Booking service | Planned | Booking saga, transactional outbox, overbooking protection |
| Realtime service | Planned | WebSocket hub for notifications and live seat counts |
| React frontend | Planned | Search, publish, bookings, live updates |
| Agent service | Planned | AI assistant that finds and auto-books rides from natural language |
| Docker, Kubernetes, CI/CD, AWS | Planned | Containers, manifests tested on Kind, GitHub Actions, deployment |

## Target architecture

Five FastAPI services, each with its **own database**, communicating over HTTP (when an answer is
needed immediately) and Redis Streams (for events).

```mermaid
flowchart TB
    Browser["React SPA (planned)"]
    Gateway["Nginx gateway (planned)"]
    subgraph Services
        Identity["Identity (built)"]
        Ride["Ride (planned)"]
        Booking["Booking (planned)"]
        Realtime["Realtime (planned)"]
        Agent["Agent (planned)"]
    end
    Redis[("Redis: rate limits, locks, event streams")]
    PG[("PostgreSQL + PostGIS: one database per service")]

    Browser --> Gateway
    Gateway --> Identity & Ride & Booking & Realtime & Agent
    Services --> Redis
    Services --> PG

    classDef built fill:#d4f4dd,stroke:#2e7d32,color:#000
    classDef planned fill:#eeeeee,stroke:#9e9e9e,stroke-dasharray: 4 3,color:#000
    class Identity built
    class Browser,Gateway,Ride,Booking,Realtime,Agent planned
```

## The Identity service (built)

### Endpoints

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/auth/register` | Public, rate limited | Create a passenger or driver account |
| POST | `/auth/login` | Public, rate limited | Verify credentials, set auth cookies |
| POST | `/auth/refresh` | Refresh cookie | Rotate the refresh token, issue a new access token |
| POST | `/auth/logout` | Any | Revoke the session and clear cookies |
| GET | `/auth/me` | Logged in | Return the current user |
| GET | `/admin/users` | Admin only | List users (paginated) |
| PATCH | `/admin/users/{id}` | Admin only | Activate/deactivate a user or change a role |
| GET | `/health`, `/health/db` | Public | Liveness and database connectivity checks |

Interactive API docs are generated automatically at `http://localhost:8001/docs`.

### Security design

- **Passwords:** hashed with Argon2id (slow and salted), computed in a worker thread so the server
  stays responsive.
- **Tokens:** short-lived (15 min) access tokens signed with **RS256**. Other services will verify
  them with the public key, so they never need to call Identity per request and cannot forge tokens.
- **Cookies:** `HttpOnly` (JavaScript cannot read them), `SameSite=Lax`, and `Secure` in production.
  The refresh cookie is scoped to `/auth` so it is not sent with every request.
- **Refresh token rotation:** 7-day, single-use tokens stored only as SHA-256 hashes. If a used token
  is presented again, the whole token family is revoked (theft detection). The "claim" step is one
  atomic `UPDATE ... RETURNING`, so concurrent requests cannot both succeed.
- **Rate limiting:** Redis sliding-window limiter implemented as a Lua script (atomic check and
  record). Applied per IP and per email, and it returns `429` with a `Retry-After` header.
- **Role-based access control:** `require_roles(...)` dependency. `401` means not logged in, `403`
  means logged in but not allowed.
- **Safe by construction:** users cannot register as admin, the API never returns the password hash,
  login failures are identical for "unknown email" and "wrong password" (with a dummy hash check so
  timing matches), and admins cannot deactivate or demote themselves.
- **Schema changes** are versioned with Alembic migrations.

## Tech stack

Python 3.11+, FastAPI, SQLAlchemy 2 (async) with asyncpg, Alembic, PostgreSQL 16 + PostGIS,
Redis 7, Argon2, PyJWT, pytest, Docker Compose.
Planned: React, Nginx, Kubernetes, GitHub Actions, AWS.

## Project structure

```
carpool-platform/
├── docker-compose.yml            Postgres+PostGIS and Redis
├── .env.example                  template for local secrets (copy to .env)
├── infra/postgres/init.sql       creates one database and one DB user per service
└── services/
    └── identity/
        ├── app/
        │   ├── main.py           app entry point
        │   ├── config.py         settings loaded from .env
        │   ├── database.py       async engine and per-request sessions
        │   ├── models.py         User and RefreshToken tables
        │   ├── schemas.py        request/response shapes
        │   ├── security.py       Argon2 hashing
        │   ├── tokens.py         JWT creation and verification
        │   ├── refresh.py        refresh-token issue and revoke
        │   ├── deps.py           get_current_user, require_roles
        │   ├── ratelimit.py      Redis sliding-window limiter
        │   └── routes/           auth.py, admin.py
        ├── alembic/versions/     database migrations
        ├── scripts/              generate_keys.py, create_admin.py
        └── tests/                integration tests
```

## Getting started (Windows with Git Bash, also works on Mac/Linux)

**Requirements:** Git, Python 3.11+, Docker Desktop.

**1. Clone and start the databases**

```bash
git clone https://github.com/YOUR_USERNAME/carpool-platform.git
cd carpool-platform
cp .env.example .env
docker compose up -d
docker compose ps
```

Wait until both containers show `healthy`. If port 5432 is already used by a Postgres installed on
your machine, change the left side of `"5432:5432"` in `docker-compose.yml` to `5433` and use 5433
in the database URL below.

**2. Set up the Identity service**

```bash
cd services/identity
python -m venv .venv
source .venv/Scripts/activate        # Mac/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Open `services/identity/.env` and set the database line to the local development value:

```
DATABASE_URL=postgresql+asyncpg://identity_user:identity_dev_pw@localhost:5432/identity_db
```

These passwords come from `infra/postgres/init.sql` and are **for local development only**.

**3. Generate signing keys, create the tables, run the service**

```bash
python scripts/generate_keys.py
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

Open http://localhost:8001/docs and try register, login, and `/auth/me`.

**4. Create an admin (optional)**

```bash
python -m scripts.create_admin
```

## Running the tests

The tests use a separate `identity_test_db` database and Redis database 1, and refuse to run
against anything else. If your Postgres volume was created before that database existed, create it once:

```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE identity_test_db OWNER identity_user;"
```

Then, from `services/identity`:

```bash
pytest -v
```

## Design decisions and trade-offs

| Decision | Why |
|---|---|
| Microservices with a database per service | Learning goal. Each service owns its data, and DB users cannot read other services' databases. |
| Seat inventory will live in the Ride service | Route and seat counts form one consistency boundary, so one local transaction can prevent overbooking. |
| RS256 instead of HS256 | Services can verify tokens without being able to create them. |
| Short access token plus rotating refresh token | Limits damage from a stolen token while keeping sessions long. |
| Real Postgres and Redis in tests, not mocks | Catches missing constraints, wrong cookie settings, and migration errors. |
| Rate limiter fails open if Redis is down | Prefers availability for login over protection. A deliberate trade-off. |
| Redis Streams instead of Kafka (planned) | Fits a small server's memory budget, with the same core concepts. |

## Known limitations

- No email verification or password reset yet.
- CSRF protection relies on `SameSite=Lax` only.
- A deactivated user's access token stays valid elsewhere for up to 15 minutes.
- Expired refresh-token rows are never cleaned up.
- The public key is read from a file; a JWKS endpoint is planned.
- No logging, metrics, or tracing yet.

## Roadmap

1. Foundations and Identity service (done)
2. Ride service: publishing, PostGIS search, reservations
3. Booking service: saga, outbox, idempotent consumers
4. Realtime service: WebSockets with Redis fan-out
5. React frontend
6. Agent service: natural-language booking and auto-booking
7. Docker images and Kubernetes manifests (tested locally on Kind)
8. CI/CD with GitHub Actions and AWS deployment

## License

Educational project.