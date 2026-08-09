from slowapi.errors import RateLimitExceeded
from .rate_limiter import (
    limiter,
    rate_limit_exceeded_handler,
)
import os
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from ..core.config import config
from ..core.engine import engine
from .rate_limiter import (
    RATE_LIMITS,
    get_rate_limit,
    limiter,
    rate_limit_exceeded_handler,
)
from slowapi.errors import RateLimitExceeded


logger = logging.getLogger(__name__)


app = FastAPI(
    title="CPS Engine API",
    description=(
        "CPS Engine - Hausa History Knowledge Graph "
        "and Digital Mallam AI."
    ),
    version=config.version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    rate_limit_exceeded_handler,
)


frontend_url = os.getenv(
    "FRONTEND_URL",
    "http://localhost:3000"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

API_KEY_NAME = "X-API-Key"

api_key_header = APIKeyHeader(
    name=API_KEY_NAME,
    auto_error=False,
)


import os

VALID_API_KEYS = {
    os.getenv("API_KEY_DEV", "dev_key_123"): {
        "plan": "free",
        "rate_limit": "5/minute",
    },
    os.getenv("API_KEY_PROD", "prod_key_456"): {
        "plan": "pro",
        "rate_limit": "100/minute",
    },
    os.getenv("API_KEY_ENTERPRISE", "enterprise_key_789"): {
        "plan": "enterprise",
        "rate_limit": "500/minute",
    },
}


async def validate_api_key(api_key: str = Depends(api_key_header)):
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required"
        )

    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return {
        "api_key": api_key,
        **VALID_API_KEYS[api_key]
}

    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Invalid API key",
                "message": (
                    "The provided API key is not valid."
                ),
            },
        )

    return {
        "api_key": api_key,
        **VALID_API_KEYS[api_key],
    }


class QueryRequest(BaseModel):
    """Single CPS Engine query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description=(
            "Natural language question about "
            "Hausa history."
        ),
    )

    context: Optional[Dict[str, Any]] = None

    use_cache: bool = True


class QueryResponse(BaseModel):
    """CPS Engine query response."""

    request_id: str
    query: str
    answer: str
    intent: Optional[str] = None
    source: Optional[str] = None
    total_results: int = 0
    timestamp: str
    response_time: float
    rate_limit: Dict[str, Any]


class BatchQueryRequest(BaseModel):
    """Batch query request."""

    queries: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
    )

    use_cache: bool = True


async def get_rate_limit_info(
    api_key: str,
) -> Dict[str, Any]:
    """Return rate-limit information."""

    plan_info = VALID_API_KEYS.get(
        api_key,
        {},
    )

    plan = plan_info.get(
        "plan",
        "free",
    )

    limits = get_rate_limit(api_key)

    return {
        "plan": plan,
        "limits": limits,
    }


@app.get("/")
async def root():
    """CPS Engine service information."""

    return {
        "name": config.app_name,
        "version": config.version,
        "status": "operational",
        "tagline": (
            "Building Tomorrow's Intelligent Apps, "
            "One Prompt at a Time"
        ),
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/v1/health")
async def health_check():
    """Check CPS Engine health."""

    health = await engine.health_check()

    return {
        "status": health["status"],
        "components": health["components"],
        "version": config.version,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }


@app.post(
    "/api/v1/query",
    response_model=QueryResponse,
)
@limiter.limit("5/minute")
async def process_query(
    request: Request,
    query_request: QueryRequest,
    api_key_info: dict = Depends(
        validate_api_key
    ),
):
    """Process one natural-language query."""

    request_id = str(uuid.uuid4())

    start_time = datetime.now(
        timezone.utc
    )

    try:
        response = await engine.process_query(
            query=query_request.query,
            context=query_request.context,
            use_cache=query_request.use_cache,
        )

        response_time = (
            datetime.now(timezone.utc)
            - start_time
        ).total_seconds()

        rate_limit_info = (
            await get_rate_limit_info(
                api_key_info["api_key"]
            )
        )

        return QueryResponse(
            request_id=request_id,
            query=query_request.query,
            answer=response.get(
                "answer",
                "",
            ),
            intent=response.get(
                "intent"
            ),
            source=response.get(
                "source"
            ),
            total_results=response.get(
                "total_results",
                0,
            ),
            timestamp=datetime.now(
                timezone.utc
            ).isoformat(),
            response_time=response_time,
            rate_limit=rate_limit_info,
        )

    except Exception as exc:
        logger.exception(
            "Query processing failed"
        )

        raise HTTPException(
            status_code=500,
            detail={
                "error": "Query processing failed",
                "message": str(exc),
                "request_id": request_id,
            },
        )


@app.post(
    "/api/v1/query/stream",
)
@limiter.limit("10/minute")
async def stream_query(
    request: Request,
    query_request: QueryRequest,
    api_key_info: dict = Depends(
        validate_api_key
    ),
):
    """Stream a CPS Engine response using SSE."""

    request_id = str(uuid.uuid4())

    async def generate():
        try:
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "request_id",
                        "request_id": request_id,
                    }
                )
                + "\n\n"
            )

            response = await engine.process_query(
                query=query_request.query,
                context=query_request.context,
                use_cache=query_request.use_cache,
            )

            answer = response.get(
                "answer",
                "",
            )

            chunk_size = 30

            for index in range(
                0,
                len(answer),
                chunk_size,
            ):
                chunk = answer[
                    index:index + chunk_size
                ]

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "chunk",
                            "content": chunk,
                        }
                    )
                    + "\n\n"
                )

                await asyncio.sleep(0.03)

            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "complete",
                        "request_id": request_id,
                        "intent": response.get(
                            "intent"
                        ),
                        "source": response.get(
                            "source"
                        ),
                    }
                )
                + "\n\n"
            )

        except Exception as exc:
            logger.exception(
                "Streaming failed"
            )

            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "error": str(exc),
                        "request_id": request_id,
                    }
                )
                + "\n\n"
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(
    "/api/v1/batch",
)
@limiter.limit("2/minute")
async def process_batch(
    request: Request,
    batch_request: BatchQueryRequest,
    api_key_info: dict = Depends(
        validate_api_key
    ),
):
    """Process up to ten queries concurrently."""

    request_id = str(uuid.uuid4())

    start_time = datetime.now(
        timezone.utc
    )

    tasks = [
        engine.process_query(
            query=query,
            use_cache=batch_request.use_cache,
        )
        for query in batch_request.queries
    ]

    responses = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    results = []

    successful = 0
    failed = 0

    for index, response in enumerate(
        responses
    ):
        if isinstance(
            response,
            Exception,
        ):
            failed += 1

            results.append(
                {
                    "index": index,
                    "error": str(response),
                }
            )

        else:
            successful += 1

            results.append(
                {
                    "index": index,
                    "query": response.get(
                        "query",
                        batch_request.queries[
                            index
                        ],
                    ),
                    "answer": response.get(
                        "answer",
                        "",
                    ),
                    "intent": response.get(
                        "intent"
                    ),
                    "source": response.get(
                        "source"
                    ),
                }
            )

    response_time = (
        datetime.now(timezone.utc)
        - start_time
    ).total_seconds()

    return {
        "request_id": request_id,
        "total": len(
            batch_request.queries
        ),
        "successful": successful,
        "failed": failed,
        "results": results,
        "response_time": response_time,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }


@app.get("/api/v1/examples")
async def get_examples():
    """Return example CPS Engine questions."""

    return {
        "examples": [
            "Who founded Kano?",
            "Tell me about Bayajidda.",
            "What are the Hausa Bakwai?",
            "Who was Queen Daurama?",
            "What is the story of Kurkuru?",
            "What advice did "
            "Muhammadu Rumfa receive?",
            "What is Hausa Ajami?",
        ]
    }


@app.get("/api/v1/metrics")
async def get_metrics():
    """Return basic engine metrics."""

    return {
        "engine": engine.get_metrics(),
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
}
