"""
Rate Limiting for CPS Engine API.

Uses SlowAPI with Redis in production
and in-memory storage as a fallback.
"""

import logging
import os
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


logger = logging.getLogger(__name__)


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379",
)


RATE_LIMITS = {
    "free": {
        "queries": "5/minute",
        "batch": "2/minute",
        "daily": "50/day",
        "streaming": "10/minute",
    },
    "pro": {
        "queries": "100/minute",
        "batch": "20/minute",
        "daily": "1000/day",
        "streaming": "50/minute",
    },
    "enterprise": {
        "queries": "500/minute",
        "batch": "100/minute",
        "daily": "10000/day",
        "streaming": "200/minute",
    },
}


def get_storage_uri() -> str:
    """
    Return the configured SlowAPI storage.

    Redis is preferred in production.
    """

    environment = os.getenv(
        "ENVIRONMENT",
        "development",
    ).lower()

    if environment == "production":
        return REDIS_URL

    return os.getenv(
        "RATE_LIMIT_STORAGE",
        "memory://",
    )


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=get_storage_uri(),
    default_limits=["100/hour"],
)


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
):
    """Return a consistent JSON response for HTTP 429."""

    retry_after = getattr(
        exc,
        "retry_after",
        None,
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": str(exc.detail),
            "retry_after": retry_after,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "suggestion": (
                "Upgrade your plan for higher limits."
            ),
        },
    )


def get_rate_limit(
    api_key: str,
) -> dict:
    """
    Get rate limits based on API key plan.

    In production, this should eventually
    come from a database.
    """

    if api_key == os.getenv(
        "API_KEY_ENTERPRISE",
        "enterprise_key_789",
    ):
        return RATE_LIMITS["enterprise"]

    if api_key == os.getenv(
        "API_KEY_PROD",
        "prod_key_456",
    ):
        return RATE_LIMITS["pro"]

    return RATE_LIMITS["free"]


def create_rate_limiters():
    """Create endpoint-specific limiters."""

    storage_uri = get_storage_uri()

    return {
        "query": Limiter(
            key_func=get_remote_address,
            storage_uri=storage_uri,
            default_limits=["5/minute"],
        ),
        "batch": Limiter(
            key_func=get_remote_address,
            storage_uri=storage_uri,
            default_limits=["2/minute"],
        ),
        "stream": Limiter(
            key_func=get_remote_address,
            storage_uri=storage_uri,
            default_limits=["10/minute"],
        ),
}
