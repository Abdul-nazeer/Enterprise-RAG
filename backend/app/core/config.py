"""
Configuration Management

Using Pydantic Settings for:
1. Type safety
2. Environment variable validation
3. Hierarchical config (dev/staging/prod)
4. Secret management
"""
from typing import Optional, List
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application Settings
    
    Design Decision: Use Pydantic Settings because:
    - Type validation at startup (fail fast)
    - Environment variable parsing
    - Secret management
    - Easy testing (can override settings)
    """
    
    # Application
    APP_NAME: str = "Enterprise RAG Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True  # Auto-reload on code changes (dev only)
    
    # Security
    SECRET_KEY: str = Field(..., min_length=32)  # Required, min 32 chars
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS (Cross-Origin Resource Sharing)
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_rag",
        description="Async PostgreSQL connection string"
    )
    DB_ECHO: bool = False  # Log SQL queries (debug only)
    
    # Redis (Cache & Celery)
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 3600  # 1 hour default cache TTL
    
    # Qdrant (Vector Database)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    VECTOR_SIZE: int = 384  # all-MiniLM-L6-v2 embedding size
    
    # LLM Configuration
    GROQ_API_KEY: Optional[str] = None  # Free Groq API
    GROQ_MODEL: str = "llama-3.1-70b-versatile"
    OLLAMA_URL: str = "http://localhost:11434"  # Local Ollama fallback
    OLLAMA_MODEL: str = "llama3.1:8b"
    
    # Embedding Model (runs locally, no API needed)
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "cpu"  # or "cuda" if GPU available
    
    # LangFuse (Observability)
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    
    # Session Management
    SESSION_TTL_HOURS: int = 24  # Auto-delete after 24 hours inactive
    MAX_UPLOAD_SIZE_MB: int = 50  # Max file size per upload
    MAX_FILES_PER_SESSION: int = 100
    MAX_DOCUMENTS_PER_SESSION: int = 100  # Max documents per session
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Celery (Background Jobs)
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v):
        """Ensure secret key is strong enough"""
        if v == "changeme" or len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters and not default")
        return v
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """Ensure using async driver"""
        if "postgresql" in v and "asyncpg" not in v:
            raise ValueError("Use asyncpg driver: postgresql+asyncpg://...")
        return v
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignore extra env vars
    )
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.ENVIRONMENT == "development"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    
    Design Decision: Use lru_cache because:
    - Settings are immutable after load
    - Avoid repeated .env file reads
    - Easy to override in tests (clear cache)
    """
    return Settings()


# Export
settings = get_settings()
