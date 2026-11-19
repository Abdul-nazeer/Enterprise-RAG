"""
Session Schemas for API Request/Response

Design Decision: Use Pydantic for:
1. Automatic validation
2. JSON serialization
3. OpenAPI schema generation
4. Type safety at API boundary
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.session import SessionState


class SessionCreate(BaseModel):
    """
    Request schema for creating a new session
    
    Design: Minimal input - server calculates everything else
    """
    # No fields needed - user_id comes from JWT token
    # Server auto-generates: id, state, timestamps, counts
    pass


class SessionUpdate(BaseModel):
    """
    Request schema for updating a session
    
    Only allow state changes (ACTIVE ↔ INACTIVE)
    """
    state: Optional[SessionState] = Field(
        None,
        description="New session state (only ACTIVE/INACTIVE allowed)"
    )


class SessionResponse(BaseModel):
    """
    Response schema for a single session
    
    Design Decision: Hide internal implementation details
    - Don't expose database internals
    - Use ISO 8601 timestamps
    - Include computed fields for UI
    """
    id: UUID = Field(description="Session unique identifier")
    user_id: UUID = Field(description="Session owner")
    state: SessionState = Field(description="Current session state")
    created_at: datetime = Field(description="Session creation time")
    expires_at: datetime = Field(description="When session expires")
    last_activity_at: datetime = Field(description="Last activity timestamp")
    document_count: int = Field(description="Number of documents uploaded")
    query_count: int = Field(description="Number of queries made")
    
    # Computed fields
    is_expired: bool = Field(description="Whether session has expired")
    is_active: bool = Field(description="Whether session is active")
    
    class Config:
        from_attributes = True  # Allow ORM model conversion
        json_encoders = {
            datetime: lambda v: v.isoformat(),  # ISO 8601 format
        }


class SessionList(BaseModel):
    """
    Response schema for list of sessions with pagination
    
    Design Decision: Always paginate lists to prevent memory issues
    """
    sessions: list[SessionResponse] = Field(description="List of sessions")
    total: int = Field(description="Total number of sessions")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    has_next: bool = Field(description="Whether there are more pages")
    
    class Config:
        from_attributes = True


class SessionStats(BaseModel):
    """
    Session statistics for dashboard/analytics
    
    Design: Aggregated metrics for monitoring
    """
    total_sessions: int = Field(description="Total sessions created")
    active_sessions: int = Field(description="Currently active sessions")
    inactive_sessions: int = Field(description="Inactive sessions")
    expired_sessions: int = Field(description="Expired sessions")
    total_documents: int = Field(description="Total documents across all sessions")
    total_queries: int = Field(description="Total queries across all sessions")
    avg_documents_per_session: float = Field(description="Average documents per session")
    avg_queries_per_session: float = Field(description="Average queries per session")
