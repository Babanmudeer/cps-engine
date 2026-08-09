import os
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


logger = logging.getLogger(__name__)


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379"
)


def get_client_identifier(request: Request) -> str:
    """
    Identify the client primarily by API key.
    Falls back to remote IP address.
    """

    api_key = request.headers.get("X-API-Key")

    if api_key:
        return f"api_key:{api_key}"

    return f"ip:{get_remote_address(request)}"


try:
    limiter = Limiter(
        key_func=get_client_identifier,
        storage_uri=REDIS_URL,
        default_limits=["100/minute"],
    )

    logger.info(
        "✅ Rate limiter initialized with Redis"
    )

except Exception as exc:
    logger.warning(
        f"Redis rate limiter initialization warning: {exc}"
    )

    limiter = Limiter(
        key_func=get_client_identifier,
        storage_uri="memory://",
        default_limits=["100/minute"],
    )


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded
):
    """
    Return a clean JSON response when
    the client exceeds the rate limit.
    """

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
            "path": request.url.path,
        },
        headers={
            "Retry-After": "60",
        },
    )
