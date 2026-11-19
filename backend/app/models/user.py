"""
User Model

Represents users who can create sessions and upload documents.

Database Table: users
Primary Key: id (UUID)
Unique: email

Why UUID instead of auto-increment integer?
- Distributed systems friendly (no ID conflicts)
- Harder to guess/enumerate users
- Can generate ID before inserting to DB
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    """
    User model for authentication and session management
    
    Table Structure:
    - id: UUID primary key
    - email: unique, indexed for fast lookup
    - hashed_password: bcrypt hash (never store plain text!)
    - full_name: optional
    - is_active: soft delete (don't actually delete users)
    - created_at, updated_at: audit trail
    
    Relationships:
    - sessions: One user can have many sessions
    """
    __tablename__ = "users"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique user identifier"
    )
    
    # Authentication
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,  # Fast lookup for login
        comment="User email (unique)"
    )
    
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="Bcrypt hashed password"
    )
    
    # Profile
    full_name = Column(
        String(255),
        nullable=True,
        comment="User's full name"
    )
    
    # Status
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="User account active status"
    )
    
    # Audit timestamps
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Account creation timestamp"
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Last update timestamp"
    )
    
    # Relationships
    # One-to-Many: One user can have many sessions
    sessions = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",  # Delete sessions when user deleted
        lazy="selectin"  # Eager load sessions (avoid N+1 queries)
    )
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"<User(id={self.id}, email={self.email})>"
    
    def __str__(self) -> str:
        """Human-readable string"""
        return self.email
