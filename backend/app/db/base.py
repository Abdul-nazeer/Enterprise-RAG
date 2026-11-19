"""
Database Base Configuration

Why we need this:
- SQLAlchemy needs a declarative base for ORM models
- Async engine for non-blocking database operations
- Session factory for dependency injection

Key Concepts:
1. Declarative Base: All models inherit from this
2. Async Engine: Non-blocking DB operations (important for FastAPI)
3. Session Factory: Creates new DB sessions per request
"""
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import text
from app.core.config import get_settings

settings = get_settings()

# ============================================
# Declarative Base
# ============================================
# All SQLAlchemy models will inherit from this
Base = declarative_base()

# ============================================
# Async Database Engine
# ============================================
# Why async?
# - FastAPI is async
# - Don't block other requests while waiting for DB
# - Better concurrency (handle more users)

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,  # Log SQL queries (debug only)
    future=True,  # Use SQLAlchemy 2.0 style
    pool_size=5,  # Connection pool size
    max_overflow=10,  # Max connections beyond pool_size
    pool_pre_ping=True,  # Check connection health before using
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# ============================================
# Session Factory
# ============================================
# Creates new session for each request
# Why sessionmaker?
# - Reusable session configuration
# - Thread-safe
# - Proper cleanup after request

async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
    autocommit=False,  # Manual commit (safer)
    autoflush=False,  # Manual flush (more control)
)


# ============================================
# Dependency for FastAPI
# ============================================
async def get_db() -> AsyncSession:
    """
    Database session dependency for FastAPI routes
    
    Usage in endpoint:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    
    Why async context manager?
    - Auto-closes session after request
    - Even if error occurs, session is cleaned up
    - Prevents connection leaks
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()  # Auto-commit if no errors
        except Exception:
            await session.rollback()  # Rollback on error
            raise
        finally:
            await session.close()  # Always close session


# ============================================
# Lifecycle Management
# ============================================

async def init_db() -> None:
    """
    Initialize database connection pool
    
    Called on application startup
    """
    # Engine is already created above, just verify connection
    async with engine.begin() as conn:
        # Test connection
        await conn.execute(text("SELECT 1"))


async def close_db() -> None:
    """
    Close database connection pool
    
    Called on application shutdown
    """
    await engine.dispose()
