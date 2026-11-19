"""
Retry Logic with Exponential Backoff

Why retry?
- Network can be flaky (database, Redis, external APIs)
- Transient errors should be retried (503, timeouts)
- Permanent errors should fail fast (404, 400)

Algorithm: Exponential Backoff with Jitter
- Retry 1: wait 1s
- Retry 2: wait 2s
- Retry 3: wait 4s
- Add random jitter to prevent thundering herd
"""
import asyncio
import logging
from functools import wraps
from typing import TypeVar, Callable, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

from app.core.exceptions import (
    DatabaseConnectionError,
    LLMServiceException,
    VectorDatabaseException,
    CacheException
)

logger = logging.getLogger(__name__)

# Type variable for generic decorator
T = TypeVar('T')


def retry_on_transient_error(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0
):
    """
    Retry decorator for transient errors
    
    Usage:
        @retry_on_transient_error(max_attempts=3)
        async def fetch_data():
            ...
    
    What gets retried:
    - Database connection errors
    - LLM API timeouts/503s
    - Vector DB connection issues
    - Redis connection errors
    
    What doesn't get retried:
    - 400 Bad Request (client error)
    - 404 Not Found (resource doesn't exist)
    - 401/403 Auth errors (fix credentials)
    """
    return retry(
        # Stop after N attempts
        stop=stop_after_attempt(max_attempts),
        
        # Exponential backoff: 1s, 2s, 4s, 8s...
        # Jitter prevents multiple clients retrying at same time
        wait=wait_exponential(
            multiplier=1,
            min=min_wait,
            max=max_wait
        ),
        
        # Only retry these specific exceptions
        retry=retry_if_exception_type((
            DatabaseConnectionError,
            LLMServiceException,
            VectorDatabaseException,
            CacheException,
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError
        )),
        
        # Log before each retry
        before_sleep=before_sleep_log(logger, logging.WARNING),
        
        # Log after final attempt
        after=after_log(logger, logging.ERROR),
        
        # Re-raise exception if all retries fail
        reraise=True
    )


def retry_on_database_error(max_attempts: int = 3):
    """
    Specialized retry for database operations
    
    Usage:
        @retry_on_database_error()
        async def create_user(db, user_data):
            ...
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((
            DatabaseConnectionError,
            ConnectionError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )


def retry_on_llm_error(max_attempts: int = 2):
    """
    Specialized retry for LLM API calls
    
    Why only 2 attempts?
    - LLM APIs can be slow (10-30s per call)
    - Don't want user waiting too long
    - After 2 failures, switch to fallback model
    
    Usage:
        @retry_on_llm_error()
        async def call_groq_api(prompt):
            ...
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type((
            LLMServiceException,
            TimeoutError,
            asyncio.TimeoutError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )


# Convenience aliases for common patterns
with_db_retry = retry_on_database_error
with_cache_retry = retry_on_transient_error


# Example usage patterns:
"""
# Pattern 1: Database operation with retry
@retry_on_database_error(max_attempts=3)
async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()

# Pattern 2: LLM call with retry + fallback
@retry_on_llm_error(max_attempts=2)
async def call_primary_llm(prompt: str):
    # Try Groq first
    return await groq_client.chat(prompt)

async def generate_with_fallback(prompt: str):
    try:
        return await call_primary_llm(prompt)
    except LLMServiceException:
        logger.warning("Primary LLM failed, using Ollama fallback")
        return await ollama_client.chat(prompt)

# Pattern 3: Vector search with retry
@retry_on_transient_error(max_attempts=3)
async def search_vectors(collection: str, query_vector: list):
    return await qdrant_client.search(
        collection_name=collection,
        query_vector=query_vector,
        limit=10
    )
"""
