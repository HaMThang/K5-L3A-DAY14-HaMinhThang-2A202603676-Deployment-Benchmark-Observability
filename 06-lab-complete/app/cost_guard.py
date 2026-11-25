"""Daily spend tracking and budget enforcement in Redis."""
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _budget_key() -> str:
    return "agent:cost:" + datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_budget() -> None:
    try:
        spent = float(r.get(_budget_key()) or 0)
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost guard service unavailable") from exc
    if spent >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = max(0, input_tokens) / 1000 * PRICE_INPUT_PER_1K + max(0, output_tokens) / 1000 * PRICE_OUTPUT_PER_1K
    try:
        key = _budget_key()
        pipe = r.pipeline(transaction=True)
        pipe.incrbyfloat(key, cost)
        pipe.expire(key, 60 * 60 * 24 * 2)
        pipe.execute()
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost tracking service unavailable") from exc
    return cost
