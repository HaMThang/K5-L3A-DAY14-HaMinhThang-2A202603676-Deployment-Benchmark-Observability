"""Redis-backed sliding-window rate limiting."""
import hashlib
import time

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


def check_rate_limit(key: str) -> None:
    now = time.time()
    window_start = now - 60
    redis_key = "agent:rate:" + hashlib.sha256(key.encode("utf-8")).hexdigest()
    try:
        pipe = r.pipeline(transaction=True)
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        count = pipe.execute()[1]
        if count >= settings.rate_limit_per_minute:
            oldest = r.zrange(redis_key, 0, 0, withscores=True)
            retry_after = max(1, int(oldest[0][1] + 60 - now + 0.999)) if oldest else 60
            raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": str(retry_after)})
        pipe = r.pipeline(transaction=True)
        pipe.zadd(redis_key, {f"{now:.6f}:{time.time_ns()}": now})
        pipe.expire(redis_key, 120)
        pipe.execute()
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate limiting service unavailable") from exc
