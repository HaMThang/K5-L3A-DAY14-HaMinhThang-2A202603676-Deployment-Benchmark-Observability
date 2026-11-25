"""Production-ready FastAPI agent entry point."""
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }
        for field in ("method", "path", "status", "ms"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload, ensure_ascii=False)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("agent")
logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
logger.handlers.clear()
logger.addHandler(handler)
logger.propagate = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("startup")
    try:
        yield
    finally:
        logger.info("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


@app.middleware("http")
async def structured_request_log(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        logger.info("request", extra={
            "method": request.method,
            "path": request.url.path,
            "status": status_code,
            "ms": round((time.perf_counter() - started) * 1000, 2),
        })


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis is unavailable")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    check_budget()
    answer = llm_ask(body.question)
    # The bundled mock has no tokenizer or provider usage data; estimate conservatively by characters.
    input_tokens = max(1, (len(body.question) + 3) // 4)
    output_tokens = max(1, (len(answer) + 3) // 4)
    record_cost(input_tokens, output_tokens)
    return {"question": body.question, "answer": answer}
