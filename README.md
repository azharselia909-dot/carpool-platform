carpool-platform/
├── docker-compose.yml           Postgres+PostGIS and Redis, one command
├── infra/postgres/init.sql      5 databases, 5 users (database-per-service)
└── services/identity/
    ├── app/
    │   ├── main.py              app entry, wires routers
    │   ├── config.py            settings from .env (fails fast if missing)
    │   ├── database.py          async engine and per-request sessions
    │   ├── models.py            User, RefreshToken tables
    │   ├── schemas.py           what the API accepts/returns (no password leaks)
    │   ├── security.py          Argon2 hashing, timing-safe check
    │   ├── tokens.py            RS256 JWT create/verify
    │   ├── refresh.py           refresh-token issue/revoke
    │   ├── deps.py              get_current_user, require_roles
    │   ├── ratelimit.py         Redis sliding-window limiter
    │   └── routes/auth.py, admin.py
    ├── alembic/versions/        2 migrations (users, refresh_tokens)
    ├── scripts/                 generate_keys.py, create_admin.py
    └── tests/                   9 integration tests