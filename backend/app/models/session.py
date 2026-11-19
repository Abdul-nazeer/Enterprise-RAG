"""
Session Model

Core model for session-based RAG system.
Each session is an isolated knowledge base for one user.

Key Concept:
- User logs in → Creates session → Uploads docs → Queries docs → Session expires
- Session data (documents, embeddings) isolated from other sessions
- Automatic cleanup after TTL expires

State Machine:
ACTIVE → INACTIVE (1h no activity) → EXPIRED (24h) → DELETED (cleanup job)
"""
import uuid
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.core.config import settings


class SessionState(str, Enum):
    """
    Session lifecycle states
    
    Why Enum?
    - Type-safe (can't set invalid state)
    - Database constraint (only valid values)
    - Easy to add new states
    """
    ACTIVE = "active"        # User currently using
    INACTIVE = "inactive"    # No activity for 1 hour
    EXPIRED = "expired"      # TTL exceeded, scheduled for deletion
    DELETED = "deleted"      # Cleaned up


class Session(Base):
    """
    Session model - isolated knowledge base per user session
    
    Table Structure:
    - id: UUID (also used as Qdrant collection name)
    - user_id: Foreign key to users table
    - state: Current session state (enum)
    - expires_at: When session should be deleted
    - last_activity_at: For detecting inactive sessions
    - document_count: Denormalized count (avoid COUNT queries)
    - query_count: Total queries in this session
    
    Relationships:
    - user: Many sessions belong to one user
    - documents: One session can have many documents
    
    Indexes:
    - (user_id, state): Fast lookup of user's active sessions
    - (state, expires_at): Cleanup job finds expired sessions
    - last_activity_at: Find inactive sessions
    """
    __tablename__ = "sessions"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Session ID (also Qdrant collection name)"
    )
    
    # Foreign Key to User
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),  # Delete sessions when user deleted
        nullable=False,
        index=True,
        comment="User who owns this session"
    )
    
    # Session State
    state = Column(
        SQLEnum(SessionState),
        default=SessionState.ACTIVE,
        nullable=False,
        index=True,
        comment="Current session state"
    )
    
    # Timestamps
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Session creation time"
    )
    
    expires_at = Column(
        DateTime,
        default=lambda: datetime.utcnow() + timedelta(hours=settings.SESSION_TTL_HOURS),
        nullable=False,
        index=True,
        comment="When session expires (auto-calculated)"
    )
    
    last_activity_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        index=True,
        comment="Last user activity (updated on each query/upload)"
    )
    
    # Statistics (Denormalized for performance)
    # Why denormalize?
    # - Avoid COUNT(*) queries (slow on large tables)
    # - O(1) access to counts
    # - Updated via triggers or application logic
    document_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of documents in this session"
    )
    
    query_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of queries made in this session"
    )
    
    # Relationships
    user = relationship(
        "User",
        back_populates="sessions"
    )
    
    documents = relationship(
        "Document",
        back_populates="session",
        cascade="all, delete-orphan",  # Delete documents when session deleted
        lazy="selectin"
    )
    
    # Composite Indexes for Performance
    # Why these indexes?
    # - Query pattern: "Find active sessions for user X"
    # - Query pattern: "Find expired sessions to cleanup"
    __table_args__ = (
        Index('idx_user_state', 'user_id', 'state'),  # User's active sessions
        Index('idx_state_expires', 'state', 'expires_at'),  # Cleanup expired
        Index('idx_last_activity', 'last_activity_at'),  # Find inactive
    )
    
    def __repr__(self) -> str:
        return f"<Session(id={self.id}, user_id={self.user_id}, state={self.state})>"
    
    @property
    def is_active(self) -> bool:
        """Check if session is currently active"""
        return self.state == SessionState.ACTIVE
    
    @property
    def is_expired(self) -> bool:
        """Check if session has expired"""
        return datetime.utcnow() > self.expires_at
    
    @property
    def time_remaining(self) -> timedelta:
        """Time until session expires"""
        return self.expires_at - datetime.utcnow()
    
    def extend_ttl(self, hours: int = None) -> None:
        """
        Extend session lifetime
        
        Use case: User is actively using session, extend it
        """
        if hours is None:
            hours = settings.SESSION_TTL_HOURS
        self.expires_at = datetime.utcnow() + timedelta(hours=hours)
    
    def mark_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_activity_at = datetime.utcnow()
