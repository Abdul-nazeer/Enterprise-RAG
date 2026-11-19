"""
Pydantic Schemas for API Request/Response

Design Decision: Separate schemas from models because:
1. API contract != Database schema
2. Request validation != Database validation
3. Response filtering (hide sensitive fields)
4. Version API independently of DB
"""
from app.schemas.session import (
    SessionCreate,
    SessionResponse,
    SessionUpdate,
    SessionList,
)

__all__ = [
    "SessionCreate",
    "SessionResponse",
    "SessionUpdate",
    "SessionList",
]
