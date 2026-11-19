"""
FastAPI Application Entry Point

Design Decisions:
1. CORS enabled for frontend (React/Vue)
2. Automatic API documentation (Swagger UI)
3. Request ID middleware for tracing
4. Error handling middleware
5. Startup/shutdown events for DB/Redis connections
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.exceptions import BaseAppException
from app.db.base import close_db, init_db
from app.db.redis import init_redis, close_redis
from app.api.routes import auth, sessions

settings = get_settings()


# ============================================
# Lifespan Events (Startup/Shutdown)
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    
    Startup:
    - Initialize database connection pool
    - Initialize Redis connection pool
    - Run database migrations (optional)
    
    Shutdown:
    - Close database connections
    - Close Redis connections
    """
    # Startup
    print("🚀 Starting Enterprise RAG Platform...")
    
    # Initialize connections
    await init_db()
    print("✅ Database connection pool initialized")
    
    await init_redis()
    print("✅ Redis connection pool initialized")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    
    await close_db()
    print("✅ Database connections closed")
    
    await close_redis()
    print("✅ Redis connections closed")


# ============================================
# FastAPI Application
# ============================================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    Enterprise RAG Platform API
    
    ## Features
    
    * **Session-Based RAG**: Isolated document collections per session
    * **Multi-Format Support**: PDF, DOCX, TXT, Markdown, Images, Code
    * **Authentication**: JWT-based auth with access/refresh tokens
    * **Caching**: Redis for hot data, PostgreSQL for persistence
    * **Vector Search**: Qdrant for semantic similarity
    * **LLM Integration**: Groq (cloud) + Ollama (local) fallback
    
    ## Authentication
    
    Most endpoints require authentication. Include Bearer token in header:
    ```
    Authorization: Bearer <your_access_token>
    ```
    
    Get tokens from `/auth/login` or `/auth/register`.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    debug=settings.DEBUG,
)


# ============================================
# CORS Middleware
# ============================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# Exception Handlers
# ============================================

@app.exception_handler(BaseAppException)
async def app_exception_handler(request: Request, exc: BaseAppException):
    """Handle custom application exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            **exc.details
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": str(exc.detail)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "details": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    # Log the error
    print(f"❌ Unexpected error: {exc}")
    
    # Don't expose internal errors in production
    if settings.is_production:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred"
            }
        )
    else:
        # Show details in development
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": exc.__class__.__name__,
                "message": str(exc)
            }
        )


# ============================================
# API Routes
# ============================================

# Health check
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Returns API status and version.
    Used by load balancers and monitoring systems.
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    API root endpoint
    
    Returns welcome message and documentation links.
    """
    return {
        "message": "Welcome to Enterprise RAG Platform API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health"
    }


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")


# ============================================
# Development Server
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level="info"
    )
