"""
Redis Connection Management

Design Decision: Single Redis instance with connection pooling
- Connection pooling for efficiency
- Async redis-py for non-blocking I/O
- Automatic reconnection on failures
"""
from typing import AsyncGenerator
from redis.asyncio import Redis, ConnectionPool
from contextlib import asynccontextmanager

from app.core.config import get_settings

settings = get_settings()

# Global connection pool (initialized once)
redis_pool: ConnectionPool = None
redis_client: Redis = None


async def init_redis() -> None:
    """
    Initialize Redis connection pool
    
    Called on application startup
    """
    global redis_pool, redis_client
    
    redis_pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=10,
    )
    
    redis_client = Redis(connection_pool=redis_pool)


async def close_redis() -> None:
    """
    Close Redis connection pool
    
    Called on application shutdown
    """
    global redis_client, redis_pool
    
    if redis_client:
        await redis_client.close()
    
    if redis_pool:
        await redis_pool.disconnect()


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    Dependency injection for Redis client
    
    Usage in FastAPI:
    ```python
    @app.get("/")
    async def handler(redis: Redis = Depends(get_redis)):
        await redis.set("key", "value")
    ```
    """
    global redis_client
    
    if redis_client is None:
        await init_redis()
    
    yield redis_client


@asynccontextmanager
async def get_redis_context():
    """
    Context manager for Redis operations
    
    Usage:
    ```python
    async with get_redis_context() as redis:
        await redis.set("key", "value")
    ```
    """
    global redis_client
    
    if redis_client is None:
        await init_redis()
    
    try:
        yield redis_client
    finally:
        pass  # Connection returns to pool automatically
