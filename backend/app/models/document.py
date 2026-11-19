"""
Document Model

Tracks uploaded documents in each session.

File Types Supported:
- PDF, DOCX, TXT, MD (text documents)
- PNG, JPG (images with OCR)
- Mermaid diagrams (.mmd)
- Code files (.py, .js, .java, etc.)

Processing Pipeline:
Upload → Parse → Chunk → Embed → Store in Qdrant → Save metadata to PostgreSQL
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, BigInteger, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class DocumentType(str, Enum):
    """
    Document type enum
    
    Used for routing to appropriate parser
    """
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "markdown"
    IMAGE = "image"
    MERMAID = "mermaid"
    CODE = "code"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    """
    Document processing status
    
    Lifecycle:
    PENDING → PROCESSING → COMPLETED
                ↓
              FAILED
    """
    PENDING = "pending"        # Uploaded, waiting to process
    PROCESSING = "processing"  # Currently being parsed/embedded
    COMPLETED = "completed"    # Ready for querying
    FAILED = "failed"          # Processing error


class Document(Base):
    """
    Document metadata model
    
    Important: This table stores METADATA only
    - Actual file content → S3/MinIO
    - Embeddings → Qdrant vector DB
    - Chunks → Also in Qdrant as payload
    
    Table Structure:
    - id: UUID
    - session_id: Which session this doc belongs to
    - filename: Original filename
    - file_type: PDF, DOCX, etc.
    - file_path: S3/MinIO path
    - file_size_bytes: For quota tracking
    - status: Processing status
    - chunk_count: How many chunks created
    - metadata: JSONB for flexible extra data
    """
    __tablename__ = "documents"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Document unique ID"
    )
    
    # Foreign Key to Session
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Session this document belongs to"
    )
    
    # File Information
    filename = Column(
        String(500),
        nullable=False,
        comment="Original filename"
    )
    
    file_type = Column(
        SQLEnum(DocumentType),
        nullable=False,
        index=True,
        comment="Document type for parser routing"
    )
    
    file_path = Column(
        String(1000),
        nullable=False,
        comment="S3/MinIO storage path"
    )
    
    file_size_bytes = Column(
        BigInteger,
        nullable=False,
        comment="File size in bytes"
    )
    
    # Processing
    status = Column(
        SQLEnum(ProcessingStatus),
        default=ProcessingStatus.PENDING,
        nullable=False,
        index=True,
        comment="Processing status"
    )
    
    error_message = Column(
        Text,
        nullable=True,
        comment="Error details if processing failed"
    )
    
    # Embeddings Info
    chunk_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of chunks created"
    )
    
    embedding_model = Column(
        String(255),
        nullable=True,
        comment="Which embedding model used"
    )
    
    # Timestamps
    uploaded_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="When file was uploaded"
    )
    
    processed_at = Column(
        DateTime,
        nullable=True,
        comment="When processing completed"
    )
    
    # Flexible metadata (JSONB for schemaless data)
    # Why JSONB?
    # - Store extra info without schema changes
    # - Can index JSON fields
    # - Queryable with PostgreSQL operators
    # Note: Can't use 'metadata' - reserved by SQLAlchemy
    extra_metadata = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Extra metadata (language, page count, etc.)"
    )
    
    # Relationships
    session = relationship(
        "Session",
        back_populates="documents"
    )
    
    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"
    
    @property
    def is_processed(self) -> bool:
        """Check if document is ready for querying"""
        return self.status == ProcessingStatus.COMPLETED
    
    @property
    def file_size_mb(self) -> float:
        """File size in MB"""
        return self.file_size_bytes / (1024 * 1024)
