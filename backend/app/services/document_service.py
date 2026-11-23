"""
Document Service - Orchestrates Document Processing Pipeline

Responsibilities:
1. File upload handling and validation
2. Parser selection and execution
3. Text chunking strategy application
4. Database storage and retrieval
5. Error handling and retries

Design Patterns:
- Service Layer Pattern (business logic orchestration)
- Strategy Pattern (chunking strategies)
- Factory Pattern (parser selection)

SOLID Principles:
- Single Responsibility: Only handles document processing orchestration
- Open/Closed: Can add new processors without modifying service
- Dependency Inversion: Depends on abstractions (BaseParser, BaseChunker)
"""
import uuid
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, BinaryIO
from datetime import datetime
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from app.models.document import Document, DocumentType, ProcessingStatus
from app.schemas.document import DocumentUpload, DocumentResponse, DocumentStats, ChunkResponse
from app.parsers import ParserFactory
from app.utils.chunking import ChunkerFactory
from app.utils.file_utils import (
    detect_file_type,
    validate_file_size,
    save_uploaded_file,
    get_file_hash
)
from app.core.config import settings
from app.core.exceptions import (
    FileProcessingException,
    FileTooLargeException,
    UnsupportedFileTypeException,
    MaxFilesExceededException,
    RecordNotFoundException,
    DatabaseException
)
from app.core.retry import with_db_retry


class DocumentService:
    """
    Service for document processing operations
    
    Workflow:
    1. Validate file (size, type, session limits)
    2. Save file temporarily
    3. Detect file type with multi-layer detection
    4. Parse document with appropriate parser
    5. Chunk text based on document type
    6. Store in database
    7. Clean up temporary files
    
    Time Complexity: O(n) where n = file size
    Space Complexity: O(m) where m = number of chunks
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize document service
        
        Args:
            db: Database session for transactions
        """
        self.db = db
        self.parser_factory = ParserFactory
        self.chunker_factory = ChunkerFactory
    
    @with_db_retry()
    async def upload_document(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        file: BinaryIO,
        filename: str,
        content_type: str
    ) -> DocumentResponse:
        """
        Upload and process a document
        
        Args:
            session_id: Session to associate document with
            user_id: User uploading the document
            file: File binary stream
            filename: Original filename
            content_type: MIME content type
        
        Returns:
            DocumentResponse with processing results
        
        Raises:
            FileTooLargeException: File exceeds size limit
            UnsupportedFileTypeException: File type not supported
            MaxFilesExceededException: Session has too many documents
            FileProcessingException: Error during processing
        """
        temp_path = None
        
        try:
            # 1. Validate session document limit
            await self._validate_document_limit(session_id)
            
            # 2. Save file temporarily
            temp_path = await save_uploaded_file(file, filename)
            
            # 3. Validate file size
            file_size = temp_path.stat().st_size
            validate_file_size(file_size, settings.MAX_FILE_SIZE_BYTES)
            
            # 4. Detect file type (multi-layer)
            detected_type = detect_file_type(temp_path)
            
            # 5. Validate file type is supported
            supported_extensions = self.parser_factory.get_supported_extensions()
            if temp_path.suffix.lower() not in supported_extensions:
                raise UnsupportedFileTypeException(
                    file_type=detected_type,
                    supported_types=list(supported_extensions)
                )
            
            # 6. Calculate file hash for deduplication
            file_hash = get_file_hash(temp_path)
            
            # 7. Check for duplicate
            existing_doc = await self._find_duplicate(session_id, file_hash)
            if existing_doc:
                logger.info(f"Duplicate document found: {existing_doc.id}")
                return self._to_response(existing_doc)
            
            # 8. Create document record (PENDING status)
            document = Document(
                id=uuid.uuid4(),
                session_id=session_id,
                user_id=user_id,
                filename=filename,
                file_size=file_size,
                file_type=self._map_document_type(temp_path.suffix),
                mime_type=content_type,
                file_hash=file_hash,
                storage_path=str(temp_path),  # Temporary, will move to permanent storage
                processing_status=ProcessingStatus.PENDING,
                created_at=datetime.utcnow()
            )
            
            self.db.add(document)
            await self.db.commit()
            await self.db.refresh(document)
            
            # 9. Process document asynchronously
            # Note: In production, use Celery task here
            processed_doc = await self._process_document(document, temp_path)
            
            return self._to_response(processed_doc)
            
        except (FileTooLargeException, UnsupportedFileTypeException, MaxFilesExceededException):
            # Re-raise validation exceptions
            raise
            
        except Exception as e:
            logger.error(f"Document upload failed: {e}", exc_info=True)
            
            # Update document status to FAILED if record exists
            if 'document' in locals():
                document.processing_status = ProcessingStatus.FAILED
                document.error_message = str(e)
                await self.db.commit()
            
            raise FileProcessingException(
                filename=filename,
                error=str(e)
            )
        
        finally:
            # Clean up temporary file
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_path}: {e}")
    
    async def _process_document(
        self,
        document: Document,
        file_path: Path
    ) -> Document:
        """
        Process document: parse → chunk → store
        
        Args:
            document: Document record
            file_path: Path to file
        
        Returns:
            Updated document with processing results
        """
        start_time = time.time()
        
        try:
            # Update status to PROCESSING
            document.processing_status = ProcessingStatus.PROCESSING
            document.processing_started_at = datetime.utcnow()
            await self.db.commit()
            
            # 1. Parse document
            logger.info(f"Parsing document {document.id}: {document.filename}")
            parser = self.parser_factory.get_parser(file_path)
            
            if not parser:
                raise FileProcessingException(
                    filename=document.filename,
                    error="No parser found for file type"
                )
            
            parse_result = parser.parse(file_path)
            
            if not parse_result.success:
                raise FileProcessingException(
                    filename=document.filename,
                    error=parse_result.error_message or "Parsing failed"
                )
            
            # 2. Select chunking strategy based on document type
            chunker = self._select_chunker(document.file_type, parse_result.text)
            
            # 3. Chunk text
            logger.info(f"Chunking document {document.id}")
            chunks = chunker.chunk(parse_result.text)
            
            # 4. Update document with results
            document.processing_status = ProcessingStatus.COMPLETED
            document.processing_completed_at = datetime.utcnow()
            document.processing_time_ms = (time.time() - start_time) * 1000
            document.total_chunks = len(chunks)
            document.char_count = len(parse_result.text)
            document.word_count = parse_result.metadata.get('word_count', 0)
            document.page_count = parse_result.metadata.get('page_count', 0)
            document.extra_metadata = {
                'parser_used': parse_result.parser_used,
                'parse_metadata': parse_result.metadata,
                'chunker_used': chunker.__class__.__name__,
                'chunk_sizes': [len(chunk['text']) for chunk in chunks]
            }
            
            # Store extracted text (for search/preview)
            document.extracted_text = parse_result.text[:10000]  # Store first 10k chars
            
            await self.db.commit()
            await self.db.refresh(document)
            
            logger.info(
                f"Document {document.id} processed successfully: "
                f"{len(chunks)} chunks in {document.processing_time_ms:.2f}ms"
            )
            
            return document
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}", exc_info=True)
            
            document.processing_status = ProcessingStatus.FAILED
            document.processing_completed_at = datetime.utcnow()
            document.error_message = str(e)
            await self.db.commit()
            
            raise
    
    def _select_chunker(self, file_type: DocumentType, text: str) -> Any:
        """
        Select appropriate chunking strategy based on document type
        
        Strategy Selection Logic:
        - CODE: Use code-aware chunking (preserve functions)
        - MARKDOWN/TXT: Use paragraph chunking
        - PDF/DOCX: Use sentence chunking (better for long docs)
        - Default: Fixed-size chunking
        
        Args:
            file_type: Type of document
            text: Text content
        
        Returns:
            Appropriate chunker instance
        """
        if file_type == DocumentType.CODE:
            return self.chunker_factory.create_chunker(
                'code',
                chunk_size=1000,
                overlap=100
            )
        elif file_type in [DocumentType.MD, DocumentType.TXT]:
            return self.chunker_factory.create_chunker(
                'paragraph',
                chunk_size=800,
                overlap=100
            )
        elif file_type in [DocumentType.PDF, DocumentType.DOCX]:
            return self.chunker_factory.create_chunker(
                'sentence',
                chunk_size=600,
                overlap=50
            )
        else:
            return self.chunker_factory.create_chunker(
                'fixed',
                chunk_size=500,
                overlap=50
            )
    
    @with_db_retry()
    async def get_document(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> DocumentResponse:
        """
        Get document by ID
        
        Args:
            document_id: Document ID
            user_id: User requesting document (for authorization)
        
        Returns:
            DocumentResponse
        
        Raises:
            RecordNotFoundException: Document not found
        """
        stmt = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id
        )
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise RecordNotFoundException("Document", str(document_id))
        
        return self._to_response(document)
    
    @with_db_retry()
    async def list_documents(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[DocumentResponse]:
        """
        List documents in a session
        
        Args:
            session_id: Session ID
            user_id: User ID (for authorization)
            skip: Pagination offset
            limit: Max results
        
        Returns:
            List of DocumentResponse
        """
        stmt = (
            select(Document)
            .where(
                Document.session_id == session_id,
                Document.user_id == user_id
            )
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        documents = result.scalars().all()
        
        return [self._to_response(doc) for doc in documents]
    
    @with_db_retry()
    async def delete_document(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """
        Delete document
        
        Args:
            document_id: Document ID
            user_id: User ID (for authorization)
        
        Returns:
            True if deleted
        
        Raises:
            RecordNotFoundException: Document not found
        """
        # First verify document exists and belongs to user
        await self.get_document(document_id, user_id)
        
        # Delete from database
        stmt = delete(Document).where(
            Document.id == document_id,
            Document.user_id == user_id
        )
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        return result.rowcount > 0
    
    @with_db_retry()
    async def get_session_stats(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> DocumentStats:
        """
        Get document statistics for a session
        
        Args:
            session_id: Session ID
            user_id: User ID
        
        Returns:
            DocumentStats with aggregated metrics
        """
        # Count by status
        stmt = (
            select(
                Document.processing_status,
                func.count(Document.id).label('count')
            )
            .where(
                Document.session_id == session_id,
                Document.user_id == user_id
            )
            .group_by(Document.processing_status)
        )
        
        result = await self.db.execute(stmt)
        status_counts = {row.processing_status: row.count for row in result}
        
        # Aggregate stats
        stmt = (
            select(
                func.count(Document.id).label('total_documents'),
                func.sum(Document.file_size).label('total_size'),
                func.sum(Document.total_chunks).label('total_chunks'),
                func.avg(Document.processing_time_ms).label('avg_processing_time')
            )
            .where(
                Document.session_id == session_id,
                Document.user_id == user_id
            )
        )
        
        result = await self.db.execute(stmt)
        stats = result.one()
        
        return DocumentStats(
            total_documents=stats.total_documents or 0,
            total_size_bytes=stats.total_size or 0,
            total_chunks=stats.total_chunks or 0,
            completed=status_counts.get(ProcessingStatus.COMPLETED, 0),
            pending=status_counts.get(ProcessingStatus.PENDING, 0),
            processing=status_counts.get(ProcessingStatus.PROCESSING, 0),
            failed=status_counts.get(ProcessingStatus.FAILED, 0),
            avg_processing_time_ms=float(stats.avg_processing_time or 0)
        )
    
    async def _validate_document_limit(self, session_id: uuid.UUID) -> None:
        """
        Validate session hasn't exceeded document limit
        
        Raises:
            MaxFilesExceededException: Too many documents
        """
        stmt = select(func.count(Document.id)).where(
            Document.session_id == session_id
        )
        result = await self.db.execute(stmt)
        count = result.scalar()
        
        if count >= settings.MAX_DOCUMENTS_PER_SESSION:
            raise MaxFilesExceededException(
                current_count=count,
                max_count=settings.MAX_DOCUMENTS_PER_SESSION
            )
    
    async def _find_duplicate(
        self,
        session_id: uuid.UUID,
        file_hash: str
    ) -> Optional[Document]:
        """
        Find duplicate document by hash
        
        Args:
            session_id: Session ID
            file_hash: File hash
        
        Returns:
            Document if found, None otherwise
        """
        stmt = select(Document).where(
            Document.session_id == session_id,
            Document.file_hash == file_hash
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    def _map_document_type(self, extension: str) -> DocumentType:
        """
        Map file extension to DocumentType enum
        
        Args:
            extension: File extension (e.g., '.pdf')
        
        Returns:
            DocumentType enum value
        """
        ext_map = {
            '.pdf': DocumentType.PDF,
            '.docx': DocumentType.DOCX,
            '.doc': DocumentType.DOCX,
            '.txt': DocumentType.TXT,
            '.md': DocumentType.MD,
            '.markdown': DocumentType.MD,
            '.png': DocumentType.IMAGE,
            '.jpg': DocumentType.IMAGE,
            '.jpeg': DocumentType.IMAGE,
            '.gif': DocumentType.IMAGE,
            '.mmd': DocumentType.MERMAID,
            '.mermaid': DocumentType.MERMAID,
            '.py': DocumentType.CODE,
            '.js': DocumentType.CODE,
            '.ts': DocumentType.CODE,
            '.java': DocumentType.CODE,
            '.cpp': DocumentType.CODE,
            '.c': DocumentType.CODE,
        }
        
        return ext_map.get(extension.lower(), DocumentType.UNKNOWN)
    
    def _to_response(self, document: Document) -> DocumentResponse:
        """
        Convert Document model to DocumentResponse schema
        
        Args:
            document: Document model
        
        Returns:
            DocumentResponse schema
        """
        return DocumentResponse(
            id=document.id,
            session_id=document.session_id,
            filename=document.filename,
            file_size=document.file_size,
            file_type=document.file_type,
            mime_type=document.mime_type,
            processing_status=document.processing_status,
            total_chunks=document.total_chunks,
            char_count=document.char_count,
            word_count=document.word_count,
            page_count=document.page_count,
            processing_time_ms=document.processing_time_ms,
            error_message=document.error_message,
            created_at=document.created_at,
            processing_started_at=document.processing_started_at,
            processing_completed_at=document.processing_completed_at
        )
