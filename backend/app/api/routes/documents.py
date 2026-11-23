"""
Document API Routes

Endpoints:
- POST /documents/upload - Upload document to session
- GET /documents - List documents in session
- GET /documents/{id} - Get document details
- DELETE /documents/{id} - Delete document
- GET /documents/stats - Get document statistics

Authentication: Required (JWT)
Authorization: User can only access own documents
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.dependencies import get_current_user, get_db
from app.services.document_service import DocumentService
from app.schemas.document import DocumentResponse, DocumentStats
from app.schemas.user import UserResponse
from app.core.exceptions import (
    FileProcessingException,
    FileTooLargeException,
    UnsupportedFileTypeException,
    MaxFilesExceededException,
    RecordNotFoundException
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document to session",
    description="""
    Upload a document to the specified session.
    
    **Features:**
    - Multi-format support (PDF, DOCX, images, code, markdown, etc.)
    - Automatic parsing and chunking
    - Deduplication (same file won't be uploaded twice)
    - Size validation (max 50MB)
    - Type detection
    
    **Process:**
    1. File validated (size, type)
    2. Temporarily saved
    3. Parsed with appropriate parser
    4. Chunked based on document type
    5. Stored in database
    
    **Returns:** Document metadata with processing results
    """
)
async def upload_document(
    session_id: uuid.UUID = Query(..., description="Session ID to upload document to"),
    file: UploadFile = File(..., description="Document file to upload"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload and process a document
    
    Raises:
        400: Invalid file or session
        413: File too large
        415: Unsupported file type
        422: Processing failed
        429: Too many files in session
    """
    try:
        # Create document service
        document_service = DocumentService(db)
        
        # Upload and process document
        logger.info(
            f"User {current_user.id} uploading {file.filename} "
            f"to session {session_id}"
        )
        
        result = await document_service.upload_document(
            session_id=session_id,
            user_id=current_user.id,
            file=file.file,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream"
        )
        
        logger.info(f"Document {result.id} uploaded successfully")
        return result
        
    except FileTooLargeException as e:
        raise e.to_http_exception()
    except UnsupportedFileTypeException as e:
        raise e.to_http_exception()
    except MaxFilesExceededException as e:
        raise e.to_http_exception()
    except FileProcessingException as e:
        raise e.to_http_exception()
    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


@router.get(
    "",
    response_model=List[DocumentResponse],
    summary="List documents in session",
    description="Retrieve all documents uploaded to a specific session"
)
async def list_documents(
    session_id: uuid.UUID = Query(..., description="Session ID"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List documents in session with pagination
    
    Returns documents ordered by creation date (newest first)
    """
    try:
        document_service = DocumentService(db)
        
        documents = await document_service.list_documents(
            session_id=session_id,
            user_id=current_user.id,
            skip=skip,
            limit=limit
        )
        
        return documents
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document by ID",
    description="Retrieve detailed information about a specific document"
)
async def get_document(
    document_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get document details
    
    Raises:
        404: Document not found or access denied
    """
    try:
        document_service = DocumentService(db)
        
        document = await document_service.get_document(
            document_id=document_id,
            user_id=current_user.id
        )
        
        return document
        
    except RecordNotFoundException as e:
        raise e.to_http_exception()
    except Exception as e:
        logger.error(f"Failed to get document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document"
        )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Permanently delete a document from the session"
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete document
    
    Also deletes associated chunks and vectors
    
    Raises:
        404: Document not found or access denied
    """
    try:
        document_service = DocumentService(db)
        
        await document_service.delete_document(
            document_id=document_id,
            user_id=current_user.id
        )
        
        logger.info(f"Document {document_id} deleted by user {current_user.id}")
        return None  # 204 No Content
        
    except RecordNotFoundException as e:
        raise e.to_http_exception()
    except Exception as e:
        logger.error(f"Failed to delete document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )


@router.get(
    "/sessions/{session_id}/stats",
    response_model=DocumentStats,
    summary="Get document statistics for session",
    description="Retrieve aggregated statistics for all documents in a session"
)
async def get_document_stats(
    session_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get document statistics
    
    Returns:
        - Total documents count
        - Total size in bytes
        - Total chunks count
        - Processing status breakdown
        - Average processing time
    """
    try:
        document_service = DocumentService(db)
        
        stats = await document_service.get_session_stats(
            session_id=session_id,
            user_id=current_user.id
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get document stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )
