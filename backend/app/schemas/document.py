"""
Document Schemas for API Request/Response

Design Decision: Separate schemas for upload, response, and processing
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.document import DocumentType, ProcessingStatus


class DocumentUpload(BaseModel):
    """
    Schema for document upload metadata
    
    Note: Actual file comes via multipart/form-data
    """
    session_id: UUID = Field(description="Session to upload document to")
    # File will be handled separately by FastAPI's UploadFile


class DocumentResponse(BaseModel):
    """
    Schema for document information in responses
    """
    id: UUID = Field(description="Document unique ID")
    session_id: UUID = Field(description="Parent session ID")
    filename: str = Field(description="Original filename")
    file_type: DocumentType = Field(description="Detected document type")
    file_size_bytes: int = Field(description="File size in bytes")
    status: ProcessingStatus = Field(description="Processing status")
    error_message: Optional[str] = Field(None, description="Error if processing failed")
    chunk_count: int = Field(description="Number of text chunks created")
    embedding_model: Optional[str] = Field(None, description="Embedding model used")
    uploaded_at: datetime = Field(description="Upload timestamp")
    processed_at: Optional[datetime] = Field(None, description="Processing completion time")
    extra_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class DocumentList(BaseModel):
    """
    Schema for list of documents with pagination
    """
    documents: list[DocumentResponse] = Field(description="List of documents")
    total: int = Field(description="Total document count")
    page: int = Field(description="Current page")
    page_size: int = Field(description="Items per page")
    has_next: bool = Field(description="More pages available")


class DocumentStats(BaseModel):
    """
    Document statistics for a session
    """
    total_documents: int = Field(description="Total documents uploaded")
    by_type: Dict[str, int] = Field(description="Count by document type")
    by_status: Dict[str, int] = Field(description="Count by processing status")
    total_chunks: int = Field(description="Total text chunks across all docs")
    total_size_bytes: int = Field(description="Total storage used")
    avg_chunks_per_document: float = Field(description="Average chunks per doc")
    processing_success_rate: float = Field(description="% of docs processed successfully")


class ChunkResponse(BaseModel):
    """
    Schema for text chunks (used in debugging/inspection)
    """
    chunk_id: str = Field(description="Unique chunk identifier")
    document_id: UUID = Field(description="Parent document ID")
    content: str = Field(description="Chunk text content")
    chunk_index: int = Field(description="Position in document (0-indexed)")
    token_count: int = Field(description="Approximate token count")
    metadata: Dict[str, Any] = Field(description="Chunk metadata (page, section, etc.)")


class ProcessingProgress(BaseModel):
    """
    Schema for processing progress updates (future: websocket)
    """
    document_id: UUID = Field(description="Document being processed")
    status: ProcessingStatus = Field(description="Current status")
    progress_percent: float = Field(description="Progress (0-100)")
    current_step: str = Field(description="Current processing step")
    error: Optional[str] = Field(None, description="Error message if failed")
