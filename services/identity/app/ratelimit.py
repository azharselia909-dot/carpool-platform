import logging
import math
import uuid

from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

from app.redis_client import redis_client

logger = logging.getLogger(__name__)

# Sliding-window log, executed atomically inside Redis.
# Each request is a member of a sorted set, scored by its timestamp in ms.
# Steps: drop entries older than the window, count what's left, then either
# reject (and report how long until a slot frees up) or record this request.
_SLIDING_WINDOW_LUA = """
local key    = KEYS[1]
local window = tonumber(ARGV[1])
local limit  = tonumber(ARGV[2])
local member = ARGV[3]

local t   = redis.call('TIME')
local now = t[1] * 1000 + math.floor(t[2] / 1000)

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry_ms = window - (now - tonumber(oldest[2]))
  return {0, retry_ms}
end

redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, window)
return {1, 0}
"""

_script = redis_client.register_script(_SLIDING_WINDOW_LUA)


async def enforce(key: str, limit: int, window_seconds: int) -> None:
    """Record one hit for `key`. Raise HTTP 429 if it exceeds `limit` per window."""
    try:
        allowed, retry_ms = await _script(
            keys=[key],
            args=[window_seconds * 1000, limit, uuid.uuid4().hex],
        )
    except RedisError:
        # Fail open: if Redis is down, let traffic through rather than lock everyone out.
        logger.exception("Rate limiter unavailable; allowing request")
        return

    if not allowed:
        retry_after = max(1, math.ceil(int(retry_ms) / 1000))
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def rate_limit(name: str, limit: int, window_seconds: int):
    """Build a FastAPI dependency that limits requests per client IP."""

    async def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        await enforce(f"rl:{name}:{ip}", limit, window_seconds)

    return dependency