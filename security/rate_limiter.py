"""
Advanced Rate Limiting and Throttling System
Provides comprehensive rate limiting with multiple algorithms and Redis backend
"""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import redis
from flask import Flask, g, request

logger = logging.getLogger(__name__)


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithms"""

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimit:
    """Rate limit configuration"""

    requests: int  # Number of requests allowed
    window: int  # Time window in seconds
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW
    burst: Optional[int] = None  # Burst capacity for token bucket
    key_prefix: str = "rate_limit"


@dataclass
class RateLimitResult:
    """Rate limit check result"""

    allowed: bool
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None
    current_usage: int = 0


class RateLimitStrategy(ABC):
    """Abstract base class for rate limiting strategies"""

    @abstractmethod
    def check_limit(self, key: str, limit: RateLimit, redis_client: redis.Redis) -> RateLimitResult:
        """Check if request is within rate limit"""
        pass


class TokenBucketStrategy(RateLimitStrategy):
    """Token bucket algorithm implementation"""

    def check_limit(self, key: str, limit: RateLimit, redis_client: redis.Redis) -> RateLimitResult:
        """Token bucket rate limiting"""
        now = time.time()
        bucket_key = f"{limit.key_prefix}:tb:{key}"

        try:
            # Lua script for atomic token bucket operations
            lua_script = """
            local bucket_key = KEYS[1]
            local capacity = tonumber(ARGV[1])
            local refill_rate = tonumber(ARGV[2])
            local requested_tokens = tonumber(ARGV[3])
            local current_time = tonumber(ARGV[4])

            local bucket_data = redis.call('HMGET', bucket_key, 'tokens', 'last_refill')
            local tokens = tonumber(bucket_data[1]) or capacity
            local last_refill = tonumber(bucket_data[2]) or current_time

            -- Calculate tokens to add based on time elapsed
            local time_elapsed = current_time - last_refill
            local tokens_to_add = math.floor(time_elapsed * refill_rate)
            tokens = math.min(capacity, tokens + tokens_to_add)

            local allowed = 0
            local remaining = tokens

            if tokens >= requested_tokens then
                tokens = tokens - requested_tokens
                allowed = 1
                remaining = tokens
            end

            -- Update bucket state
            redis.call('HMSET', bucket_key, 'tokens', tokens, 'last_refill', current_time)
            redis.call('EXPIRE', bucket_key, capacity)

            return {allowed, remaining, capacity}
            """

            capacity = limit.burst or limit.requests
            refill_rate = limit.requests / limit.window  # tokens per second

            result = redis_client.eval(lua_script, 1, bucket_key, capacity, refill_rate, 1, now)  # requesting 1 token

            allowed, remaining, _ = result
            reset_time = int(now + limit.window)

            return RateLimitResult(
                allowed=bool(allowed),
                remaining=int(remaining),
                reset_time=reset_time,
                retry_after=None if allowed else int(1 / refill_rate),
                current_usage=capacity - int(remaining),
            )

        except Exception as e:
            logger.error(f"Token bucket rate limit error: {e}")
            # Fail open - allow request
            return RateLimitResult(allowed=True, remaining=limit.requests, reset_time=int(now + limit.window))


class SlidingWindowStrategy(RateLimitStrategy):
    """Sliding window log algorithm"""

    def check_limit(self, key: str, limit: RateLimit, redis_client: redis.Redis) -> RateLimitResult:
        """Sliding window rate limiting"""
        now = time.time()
        window_key = f"{limit.key_prefix}:sw:{key}"

        try:
            # Lua script for atomic sliding window operations
            lua_script = """
            local window_key = KEYS[1]
            local window_size = tonumber(ARGV[1])
            local max_requests = tonumber(ARGV[2])
            local current_time = tonumber(ARGV[3])
            local window_start = current_time - window_size

            -- Remove expired entries
            redis.call('ZREMRANGEBYSCORE', window_key, '-inf', window_start)

            -- Count current requests in window
            local current_count = redis.call('ZCARD', window_key)

            local allowed = 0
            if current_count < max_requests then
                -- Add current request
                redis.call('ZADD', window_key, current_time, current_time .. ':' .. math.random())
                allowed = 1
                current_count = current_count + 1
            end

            -- Set expiration
            redis.call('EXPIRE', window_key, window_size + 1)

            local remaining = math.max(0, max_requests - current_count)
            return {allowed, remaining, current_count}
            """

            result = redis_client.eval(lua_script, 1, window_key, limit.window, limit.requests, now)

            allowed, remaining, current_count = result
            reset_time = int(now + limit.window)

            return RateLimitResult(
                allowed=bool(allowed),
                remaining=int(remaining),
                reset_time=reset_time,
                retry_after=None if allowed else 1,
                current_usage=int(current_count),
            )

        except Exception as e:
            logger.error(f"Sliding window rate limit error: {e}")
            # Fail open
            return RateLimitResult(allowed=True, remaining=limit.requests, reset_time=int(now + limit.window))


class FixedWindowStrategy(RateLimitStrategy):
    """Fixed window counter algorithm"""

    def check_limit(self, key: str, limit: RateLimit, redis_client: redis.Redis) -> RateLimitResult:
        """Fixed window rate limiting"""
        now = time.time()
        window_start = int(now // limit.window) * limit.window
        window_key = f"{limit.key_prefix}:fw:{key}:{window_start}"

        try:
            # Lua script for atomic counter operations
            lua_script = """
            local counter_key = KEYS[1]
            local max_requests = tonumber(ARGV[1])
            local window_size = tonumber(ARGV[2])

            local current_count = redis.call('GET', counter_key) or 0
            current_count = tonumber(current_count)

            local allowed = 0
            if current_count < max_requests then
                current_count = redis.call('INCR', counter_key)
                redis.call('EXPIRE', counter_key, window_size)
                allowed = 1
            end

            local remaining = math.max(0, max_requests - current_count)
            return {allowed, remaining, current_count}
            """

            result = redis_client.eval(lua_script, 1, window_key, limit.requests, limit.window)

            allowed, remaining, current_count = result
            reset_time = window_start + limit.window

            return RateLimitResult(
                allowed=bool(allowed),
                remaining=int(remaining),
                reset_time=int(reset_time),
                retry_after=None if allowed else int(reset_time - now),
                current_usage=int(current_count),
            )

        except Exception as e:
            logger.error(f"Fixed window rate limit error: {e}")
            # Fail open
            return RateLimitResult(allowed=True, remaining=limit.requests, reset_time=int(now + limit.window))


class RateLimiter:
    """Advanced rate limiter with multiple algorithms and Redis backend"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or self._get_redis_client()
        self.strategies = {
            RateLimitAlgorithm.TOKEN_BUCKET: TokenBucketStrategy(),
            RateLimitAlgorithm.SLIDING_WINDOW: SlidingWindowStrategy(),
            RateLimitAlgorithm.FIXED_WINDOW: FixedWindowStrategy(),
        }

        # Rate limit configurations
        self.limits: Dict[str, RateLimit] = {}

    def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client with fallback"""
        try:
            return redis.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", "6379")),
                password=os.environ.get("REDIS_PASSWORD"),
                db=int(os.environ.get("RATE_LIMIT_REDIS_DB", "2")),
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
        except Exception as e:
            logger.error(f"Failed to connect to Redis for rate limiting: {e}")
            return None

    def add_limit(self, name: str, limit: RateLimit) -> None:
        """Add a rate limit configuration"""
        self.limits[name] = limit
        logger.info(f"Added rate limit '{name}': {limit.requests} requests per {limit.window}s")

    def check_limit(self, limit_name: str, key: str) -> RateLimitResult:
        """Check if request is within rate limit"""
        if not self.redis_client:
            # Fail open if Redis is not available
            return RateLimitResult(allowed=True, remaining=100, reset_time=int(time.time() + 60))

        limit = self.limits.get(limit_name)
        if not limit:
            logger.warning(f"Rate limit '{limit_name}' not found")
            return RateLimitResult(allowed=True, remaining=100, reset_time=int(time.time() + 60))

        strategy = self.strategies.get(limit.algorithm)
        if not strategy:
            logger.error(f"Rate limiting strategy '{limit.algorithm}' not implemented")
            return RateLimitResult(allowed=True, remaining=limit.requests, reset_time=int(time.time() + limit.window))

        return strategy.check_limit(key, limit, self.redis_client)

    def reset_limit(self, limit_name: str, key: str) -> bool:
        """Reset rate limit for a specific key"""
        if not self.redis_client:
            return False

        limit = self.limits.get(limit_name)
        if not limit:
            return False

        try:
            # Remove all keys associated with this limit and key
            patterns = [f"{limit.key_prefix}:tb:{key}", f"{limit.key_prefix}:sw:{key}", f"{limit.key_prefix}:fw:{key}:*"]

            for pattern in patterns:
                if "*" in pattern:
                    keys = self.redis_client.keys(pattern)
                    if keys:
                        self.redis_client.delete(*keys)
                else:
                    self.redis_client.delete(pattern)

            logger.info(f"Reset rate limit '{limit_name}' for key '{key}'")
            return True

        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")
            return False


# Flask integration
def create_rate_limiter_from_config(config: Dict[str, Any]) -> RateLimiter:
    """Create rate limiter from configuration"""
    limiter = RateLimiter()

    for name, limit_config in config.items():
        algorithm = RateLimitAlgorithm(limit_config.get("algorithm", "sliding_window"))

        limit = RateLimit(
            requests=limit_config["requests"],
            window=limit_config["window"],
            algorithm=algorithm,
            burst=limit_config.get("burst"),
            key_prefix=limit_config.get("key_prefix", "rate_limit"),
        )

        limiter.add_limit(name, limit)

    return limiter


def get_rate_limit_key(strategy: str = "ip") -> str:
    """Generate rate limit key based on strategy"""
    if strategy == "ip":
        return request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)
    elif strategy == "user":
        user = getattr(g, "current_user", None)
        if user:
            return f"user:{user['id']}"
        return get_rate_limit_key("ip")  # Fallback to IP
    elif strategy == "api_key":
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api_key:{api_key}"
        return get_rate_limit_key("ip")  # Fallback to IP
    else:
        return request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)


# Default rate limiter instance
rate_limiter = RateLimiter()


def init_default_limits():
    """Initialize default rate limits"""
    # Global rate limit
    rate_limiter.add_limit("global", RateLimit(requests=100, window=60, algorithm=RateLimitAlgorithm.SLIDING_WINDOW))

    # API rate limit
    rate_limiter.add_limit("api", RateLimit(requests=30, window=60, algorithm=RateLimitAlgorithm.SLIDING_WINDOW))

    # Authentication rate limit
    rate_limiter.add_limit("auth", RateLimit(requests=5, window=60, algorithm=RateLimitAlgorithm.FIXED_WINDOW))

    # Premium users get higher limits
    rate_limiter.add_limit("premium", RateLimit(requests=200, window=60, algorithm=RateLimitAlgorithm.TOKEN_BUCKET, burst=50))


# Initialize default limits
init_default_limits()
