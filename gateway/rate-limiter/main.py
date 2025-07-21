import hashlib
import json
import os
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import redis
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, validator

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "1"))
DEFAULT_RATE_LIMIT = int(os.getenv("DEFAULT_RATE_LIMIT", "1000"))
DEFAULT_WINDOW = int(os.getenv("DEFAULT_WINDOW", "3600"))  # 1 hour
BURST_MULTIPLIER = float(os.getenv("BURST_MULTIPLIER", "2.0"))

# Logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Redis setup
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# Metrics
rate_limit_checks = Counter("rate_limit_checks_total", "Total rate limit checks", ["result"])
rate_limit_exceeded = Counter("rate_limit_exceeded_total", "Rate limit exceeded events", ["type"])
rate_limit_duration = Histogram("rate_limit_check_duration_seconds", "Rate limit check duration")
active_rate_limits = Gauge("active_rate_limits", "Currently active rate limits")


# Models
class RateLimitType(str, Enum):
    IP = "ip"
    USER = "user"
    API_KEY = "api_key"
    ENDPOINT = "endpoint"
    GLOBAL = "global"


class RateLimitRule(BaseModel):
    type: RateLimitType
    identifier: str
    limit: int
    window: int  # seconds
    burst_limit: Optional[int] = None

    @validator("burst_limit", always=True)
    def set_burst_limit(cls, v, values):
        if v is None and "limit" in values:
            return int(values["limit"] * BURST_MULTIPLIER)
        return v


class RateLimitStatus(BaseModel):
    allowed: bool
    limit: int
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None


class RateLimitConfig(BaseModel):
    rules: List[RateLimitRule]
    default_limit: int = DEFAULT_RATE_LIMIT
    default_window: int = DEFAULT_WINDOW


# FastAPI app
app = FastAPI(title="Rate Limiting Service", description="Distributed rate limiting for API Gateway", version="1.0.0")


class RateLimiter:
    def __init__(self):
        self.redis = redis_client
        self.default_rules = {
            RateLimitType.GLOBAL: RateLimitRule(
                type=RateLimitType.GLOBAL, identifier="*", limit=DEFAULT_RATE_LIMIT, window=DEFAULT_WINDOW
            ),
            RateLimitType.IP: RateLimitRule(type=RateLimitType.IP, identifier="*", limit=500, window=3600),
            RateLimitType.USER: RateLimitRule(type=RateLimitType.USER, identifier="*", limit=2000, window=3600),
            RateLimitType.API_KEY: RateLimitRule(type=RateLimitType.API_KEY, identifier="*", limit=5000, window=3600),
        }

    def _get_key(self, rule_type: RateLimitType, identifier: str, window_start: int) -> str:
        """Generate Redis key for rate limit tracking"""
        return f"rate_limit:{rule_type.value}:{identifier}:{window_start}"

    def _get_window_start(self, window: int) -> int:
        """Get the start of the current window"""
        return int(time.time() // window) * window

    def _sliding_window_check(self, rule: RateLimitRule, identifier: str) -> RateLimitStatus:
        """Implement sliding window rate limiting"""
        now = time.time()
        window_start = self._get_window_start(rule.window)
        prev_window_start = window_start - rule.window

        current_key = self._get_key(rule.type, identifier, window_start)
        prev_key = self._get_key(rule.type, identifier, prev_window_start)

        pipe = self.redis.pipeline()
        pipe.get(current_key)
        pipe.get(prev_key)
        results = pipe.execute()

        current_count = int(results[0] or 0)
        prev_count = int(results[1] or 0)

        # Calculate weighted count for sliding window
        elapsed_in_window = now - window_start
        weight = 1.0 - (elapsed_in_window / rule.window)
        weighted_prev_count = prev_count * weight
        total_count = current_count + weighted_prev_count

        # Check if limit exceeded
        if total_count >= rule.limit:
            rate_limit_checks.labels(result="exceeded").inc()
            rate_limit_exceeded.labels(type=rule.type.value).inc()

            reset_time = window_start + rule.window
            retry_after = int(reset_time - now)

            return RateLimitStatus(
                allowed=False, limit=rule.limit, remaining=0, reset_time=reset_time, retry_after=max(retry_after, 1)
            )

        # Increment counter
        pipe = self.redis.pipeline()
        pipe.incr(current_key)
        pipe.expire(current_key, rule.window * 2)  # Keep for 2 windows
        pipe.execute()

        rate_limit_checks.labels(result="allowed").inc()

        remaining = max(0, rule.limit - int(total_count) - 1)
        reset_time = window_start + rule.window

        return RateLimitStatus(allowed=True, limit=rule.limit, remaining=remaining, reset_time=reset_time)

    def check_rate_limit(
        self, rule_type: RateLimitType, identifier: str, custom_rule: Optional[RateLimitRule] = None
    ) -> RateLimitStatus:
        """Check if request is within rate limit"""
        with rate_limit_duration.time():
            # Use custom rule or default
            rule = custom_rule or self.default_rules.get(rule_type)
            if not rule:
                # If no rule found, allow by default
                return RateLimitStatus(
                    allowed=True, limit=float("inf"), remaining=float("inf"), reset_time=int(time.time()) + 3600
                )

            return self._sliding_window_check(rule, identifier)

    def get_rule(self, rule_type: RateLimitType, identifier: str) -> Optional[RateLimitRule]:
        """Get specific rule for type and identifier"""
        # First check for specific rule
        rule_key = f"rule:{rule_type.value}:{identifier}"
        rule_data = self.redis.get(rule_key)

        if rule_data:
            try:
                return RateLimitRule.parse_raw(rule_data)
            except Exception:
                logger.error("Failed to parse rule", rule_key=rule_key)

        # Fall back to default rule
        return self.default_rules.get(rule_type)

    def set_rule(self, rule: RateLimitRule, ttl: Optional[int] = None):
        """Set a custom rate limiting rule"""
        rule_key = f"rule:{rule.type.value}:{rule.identifier}"
        rule_data = rule.json()

        if ttl:
            self.redis.setex(rule_key, ttl, rule_data)
        else:
            self.redis.set(rule_key, rule_data)

        logger.info("Rate limit rule set", rule=rule.dict())

    def delete_rule(self, rule_type: RateLimitType, identifier: str):
        """Delete a custom rate limiting rule"""
        rule_key = f"rule:{rule_type.value}:{identifier}"
        self.redis.delete(rule_key)
        logger.info("Rate limit rule deleted", type=rule_type.value, identifier=identifier)

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiting statistics"""
        stats = {}

        # Get active rate limits
        pattern = "rate_limit:*"
        keys = self.redis.keys(pattern)
        active_rate_limits.set(len(keys))

        # Group by type
        by_type = {}
        for key in keys:
            parts = key.split(":")
            if len(parts) >= 3:
                rate_type = parts[1]
                if rate_type not in by_type:
                    by_type[rate_type] = 0
                by_type[rate_type] += 1

        stats["active_limits_by_type"] = by_type
        stats["total_active_limits"] = len(keys)

        return stats


# Global rate limiter instance
rate_limiter = RateLimiter()


# Routes
@app.get("/health")
async def health_check():
    try:
        redis_client.ping()
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unavailable")


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/check")
async def check_rate_limit(rule_type: RateLimitType, identifier: str, custom_rule: Optional[RateLimitRule] = None):
    """Check if request is within rate limit"""
    try:
        result = rate_limiter.check_rate_limit(rule_type, identifier, custom_rule)

        return {
            "allowed": result.allowed,
            "limit": result.limit,
            "remaining": result.remaining,
            "reset_time": result.reset_time,
            "retry_after": result.retry_after,
        }
    except Exception as e:
        logger.error("Rate limit check failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/rules")
async def create_rule(rule: RateLimitRule, ttl: Optional[int] = None):
    """Create or update a rate limiting rule"""
    try:
        rate_limiter.set_rule(rule, ttl)
        return {"message": "Rule created successfully", "rule": rule.dict()}
    except Exception as e:
        logger.error("Failed to create rule", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/rules/{rule_type}/{identifier}")
async def get_rule(rule_type: RateLimitType, identifier: str):
    """Get a specific rate limiting rule"""
    try:
        rule = rate_limiter.get_rule(rule_type, identifier)
        if rule:
            return {"rule": rule.dict()}
        else:
            raise HTTPException(status_code=404, detail="Rule not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get rule", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/rules/{rule_type}/{identifier}")
async def delete_rule(rule_type: RateLimitType, identifier: str):
    """Delete a rate limiting rule"""
    try:
        rate_limiter.delete_rule(rule_type, identifier)
        return {"message": "Rule deleted successfully"}
    except Exception as e:
        logger.error("Failed to delete rule", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/stats")
async def get_stats():
    """Get rate limiting statistics"""
    try:
        stats = rate_limiter.get_stats()
        return stats
    except Exception as e:
        logger.error("Failed to get stats", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    logger.info(
        "Request processed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        process_time=process_time,
    )

    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
