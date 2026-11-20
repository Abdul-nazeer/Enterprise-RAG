"""
File Utilities for Type Detection and Validation

Design Decision: Multi-layer type detection for accuracy
1. File extension (fastest, least reliable)
2. MIME type detection (filetype library)
3. Magic bytes (python-magic)
4. Content analysis (for text files)

Why multiple layers?
- User can rename .txt to .pdf (extension unreliable)
- MIME types can be spoofed
- Magic bytes are most reliable but slower
- Combination gives high confidence
"""
import os
import filetype
import mimetypes
from pathlib import Path
from typing import Optional, Tuple
import chardet

from app.models.document import DocumentType
from app.core.config import get_settings

settings = get_settings()

# File type mappings
EXTENSION_TO_TYPE = {
    # Documents
    '.pdf': DocumentType.PDF,
    '.docx': DocumentType.DOCX,
    '.doc': DocumentType.DOCX,
    '.txt': DocumentType.TXT,
    '.md': DocumentType.MD,
    '.markdown': DocumentType.MD,
    
    # Images
    '.png': DocumentType.IMAGE,
    '.jpg': DocumentType.IMAGE,
    '.jpeg': DocumentType.IMAGE,
    '.gif': DocumentType.IMAGE,
    '.bmp': DocumentType.IMAGE,
    '.tiff': DocumentType.IMAGE,
    '.webp': DocumentType.IMAGE,
    
    # Code
    '.py': DocumentType.CODE,
    '.js': DocumentType.CODE,
    '.ts': DocumentType.CODE,
    '.java': DocumentType.CODE,
    '.cpp': DocumentType.CODE,
    '.c': DocumentType.CODE,
    '.go': DocumentType.CODE,
    '.rs': DocumentType.CODE,
    '.rb': DocumentType.CODE,
    '.php': DocumentType.CODE,
    '.swift': DocumentType.CODE,
    '.kt': DocumentType.CODE,
    '.scala': DocumentType.CODE,
    '.sh': DocumentType.CODE,
    '.yaml': DocumentType.CODE,
    '.yml': DocumentType.CODE,
    '.json': DocumentType.CODE,
    '.xml': DocumentType.CODE,
    '.html': DocumentType.CODE,
    '.css': DocumentType.CODE,
    '.sql': DocumentType.CODE,
    
    # Mermaid
    '.mmd': DocumentType.MERMAID,
    '.mermaid': DocumentType.MERMAID,
}

MIME_TO_TYPE = {
    'application/pdf': DocumentType.PDF,
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': DocumentType.DOCX,
    'application/msword': DocumentType.DOCX,
    'text/plain': DocumentType.TXT,
    'text/markdown': DocumentType.MD,
    'image/png': DocumentType.IMAGE,
    'image/jpeg': DocumentType.IMAGE,
    'image/gif': DocumentType.IMAGE,
    'image/bmp': DocumentType.IMAGE,
    'image/tiff': DocumentType.IMAGE,
    'image/webp': DocumentType.IMAGE,
    'text/x-python': DocumentType.CODE,
    'application/x-python-code': DocumentType.CODE,
    'text/x-java-source': DocumentType.CODE,
    'text/x-c': DocumentType.CODE,
    'text/x-c++': DocumentType.CODE,
    'application/javascript': DocumentType.CODE,
    'text/javascript': DocumentType.CODE,
    'application/json': DocumentType.CODE,
    'text/html': DocumentType.CODE,
    'text/css': DocumentType.CODE,
    'application/xml': DocumentType.CODE,
    'text/xml': DocumentType.CODE,
}


def detect_file_type(file_path: Path) -> str:
    """
    Detect file type using multiple methods
    
    Algorithm:
    1. Check file extension (confidence: 0.3)
    2. Check MIME type with filetype (confidence: 0.5)
    3. Check magic bytes with python-magic (confidence: 0.7)
    4. Analyze content for text files (confidence: 0.9)
    5. Return highest confidence detection
    
    Returns:
        String representation of file type (e.g., 'application/pdf')
    
    Time Complexity: O(1) for extension, O(n) for content analysis
    """
    # Convert to string for compatibility
    file_path_str = str(file_path)
    original_filename = file_path.name
    
    detections = []
    
    # Method 1: File extension
    ext = Path(original_filename).suffix.lower()
    if ext in EXTENSION_TO_TYPE:
        detections.append((EXTENSION_TO_TYPE[ext], 0.3, 'extension'))
    
    # Method 2: filetype library (magic bytes)
    try:
        kind = filetype.guess(file_path_str)
        if kind is not None:
            mime = kind.mime
            if mime in MIME_TO_TYPE:
                detections.append((MIME_TO_TYPE[mime], 0.7, 'magic_bytes'))
    except Exception:
        pass
    
    # Method 3: mimetypes library
    try:
        mime, _ = mimetypes.guess_type(original_filename)
        if mime and mime in MIME_TO_TYPE:
            detections.append((MIME_TO_TYPE[mime], 0.5, 'mime_type'))
    except Exception:
        pass
    
    # Method 4: Content analysis for text files
    if _is_text_file(file_path_str):
        # Check if it's code, markdown, or plain text
        with open(file_path_str, 'rb') as f:
            content = f.read(4096)  # Read first 4KB
            
        try:
            text = content.decode('utf-8')
            
            # Check for Mermaid syntax
            if 'graph' in text.lower() or 'flowchart' in text.lower() or 'sequenceDiagram' in text:
                detections.append((DocumentType.MERMAID, 0.9, 'content_analysis'))
            # Check for Markdown syntax
            elif any(marker in text for marker in ['# ', '## ', '```', '[', '](', '**', '__']):
                detections.append((DocumentType.MD, 0.9, 'content_analysis'))
            # Check for code patterns
            elif _has_code_patterns(text):
                detections.append((DocumentType.CODE, 0.85, 'content_analysis'))
            else:
                detections.append((DocumentType.TXT, 0.8, 'content_analysis'))
        except:
            detections.append((DocumentType.TXT, 0.6, 'text_fallback'))
    
    # Return detection with highest confidence (as string)
    if detections:
        best_detection = max(detections, key=lambda x: x[1])
        return str(best_detection[0].value) if hasattr(best_detection[0], 'value') else str(best_detection[0])
    
    # Fallback: UNKNOWN
    return 'unknown'


def _is_text_file(file_path: str, sample_size: int = 8192) -> bool:
    """
    Check if file is text-based by analyzing first N bytes
    
    Algorithm: Check for null bytes (binary indicator)
    - Text files: mostly printable ASCII/UTF-8
    - Binary files: contain null bytes
    
    Time Complexity: O(n) where n = sample_size
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(sample_size)
            
        # Check for null bytes (binary indicator)
        if b'\x00' in chunk:
            return False
        
        # Try to decode as text
        try:
            chunk.decode('utf-8')
            return True
        except UnicodeDecodeError:
            # Try other encodings
            try:
                detected = chardet.detect(chunk)
                if detected['confidence'] > 0.7:
                    return True
            except:
                pass
        
        return False
    except Exception:
        return False


def _has_code_patterns(text: str) -> bool:
    """
    Detect if text contains code patterns
    
    Heuristics:
    - Function definitions: def, function, func, class, interface
    - Common keywords: import, return, if, else, while, for
    - Operators: ==, !=, <=, >=, &&, ||
    - Brackets: {}, (), []
    
    Time Complexity: O(n) where n = text length
    """
    code_indicators = [
        'def ', 'class ', 'function ', 'func ', 'interface ',
        'import ', 'from ', 'return ', 'yield ',
        'if (', 'else {', 'while (', 'for (', 'for i in',
        '== ', '!= ', '<= ', '>= ', '&& ', '|| ',
        '{}', '()', '[]',
        ';', '::',
    ]
    
    # Count matches
    matches = sum(1 for indicator in code_indicators if indicator in text)
    
    # If >30% of indicators found, likely code
    threshold = len(code_indicators) * 0.3
    return matches >= threshold



def get_safe_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks
    
    Security: Remove ../, /, \\ and other dangerous characters
    
    Time Complexity: O(n)
    """
    # Remove path separators
    filename = os.path.basename(filename)
    
    # Remove dangerous characters
    dangerous_chars = ['..', '/', '\\', '\0', '<', '>', ':', '"', '|', '?', '*']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    
    return filename


def detect_encoding(file_path: str) -> str:
    """
    Detect text file encoding
    
    Uses chardet library for high accuracy
    
    Returns: encoding name (e.g., 'utf-8', 'latin-1')
    """
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(100000)  # Read first 100KB
        
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        confidence = result['confidence']
        
        # Fallback to utf-8 if low confidence
        if confidence < 0.7:
            return 'utf-8'
        
        return encoding or 'utf-8'
    except Exception:
        return 'utf-8'


def get_file_extension_from_type(doc_type: DocumentType) -> str:
    """
    Get default file extension for document type
    
    Used when storing processed files
    """
    extension_map = {
        DocumentType.PDF: '.pdf',
        DocumentType.DOCX: '.docx',
        DocumentType.TXT: '.txt',
        DocumentType.MD: '.md',
        DocumentType.IMAGE: '.png',
        DocumentType.MERMAID: '.mmd',
        DocumentType.CODE: '.txt',
        DocumentType.UNKNOWN: '.bin',
    }
    return extension_map.get(doc_type, '.bin')



async def save_uploaded_file(file: BinaryIO, filename: str) -> Path:
    """
    Save uploaded file to temporary location
    
    Args:
        file: File binary stream
        filename: Original filename
    
    Returns:
        Path to saved temporary file
    
    Security: Use safe filename and temp directory
    """
    import tempfile
    import shutil
    
    # Get safe filename
    safe_name = get_safe_filename(filename)
    
    # Create temp directory if doesn't exist
    temp_dir = Path(tempfile.gettempdir()) / "rag_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename to avoid collisions
    import uuid
    unique_name = f"{uuid.uuid4()}_{safe_name}"
    temp_path = temp_dir / unique_name
    
    # Save file
    with open(temp_path, 'wb') as buffer:
        shutil.copyfileobj(file, buffer)
    
    return temp_path


def get_file_hash(file_path: Path) -> str:
    """
    Calculate SHA-256 hash of file for deduplication
    
    Args:
        file_path: Path to file
    
    Returns:
        Hex string of file hash
    
    Time Complexity: O(n) where n = file size
    """
    import hashlib
    
    sha256_hash = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()


def validate_file_size(file_size: int, max_size: int) -> None:
    """
    Validate file size and raise exception if invalid
    
    Args:
        file_size: Size in bytes
        max_size: Maximum allowed size in bytes
    
    Raises:
        FileTooLargeException: If file too large
    """
    from app.core.exceptions import FileTooLargeException
    
    if file_size == 0:
        raise FileTooLargeException(file_size, max_size)
    
    if file_size > max_size:
        raise FileTooLargeException(file_size, max_size)
