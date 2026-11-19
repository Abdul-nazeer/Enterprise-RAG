"""
Base Parser Interface

Design Pattern: Strategy Pattern + Template Method
- Defines common interface for all parsers
- Handles error recovery
- Provides structured output
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path


@dataclass
class ParseResult:
    """
    Structured result from document parsing
    
    Design: Rich metadata for better processing
    """
    # Core content
    text: str = ""
    
    # Structural elements
    pages: List[Dict[str, Any]] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    images: List[Dict[str, Any]] = field(default_factory=list)
    code_blocks: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Processing info
    success: bool = True
    error_message: Optional[str] = None
    parser_used: str = "unknown"
    processing_time_ms: float = 0.0
    
    def __post_init__(self):
        """Calculate derived metadata"""
        if self.text:
            self.metadata['char_count'] = len(self.text)
            self.metadata['word_count'] = len(self.text.split())
            self.metadata['page_count'] = len(self.pages)
            self.metadata['section_count'] = len(self.sections)
            self.metadata['table_count'] = len(self.tables)
            self.metadata['image_count'] = len(self.images)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'text': self.text,
            'pages': self.pages,
            'sections': self.sections,
            'tables': self.tables,
            'images': self.images,
            'code_blocks': self.code_blocks,
            'metadata': self.metadata,
            'success': self.success,
            'error_message': self.error_message,
            'parser_used': self.parser_used,
            'processing_time_ms': self.processing_time_ms,
        }


class BaseParser(ABC):
    """
    Abstract base class for all document parsers
    
    Responsibilities:
    1. Parse document into structured format
    2. Extract text and metadata
    3. Handle errors gracefully
    4. Provide consistent interface
    """
    
    def __init__(self):
        self.parser_name = self.__class__.__name__
    
    @abstractmethod
    def parse(self, file_path: str, **kwargs) -> ParseResult:
        """
        Parse document and return structured result
        
        Args:
            file_path: Path to document file
            **kwargs: Parser-specific options
        
        Returns:
            ParseResult with extracted content and metadata
        
        Raises:
            Should catch exceptions and return ParseResult with error
        """
        pass
    
    def validate_file(self, file_path: str) -> bool:
        """
        Validate file exists and is readable
        
        Returns: True if valid, False otherwise
        """
        try:
            path = Path(file_path)
            return path.exists() and path.is_file() and path.stat().st_size > 0
        except Exception:
            return False
    
    def _create_error_result(self, error_message: str) -> ParseResult:
        """
        Create ParseResult for error cases
        
        Helper method for consistent error handling
        """
        return ParseResult(
            success=False,
            error_message=error_message,
            parser_used=self.parser_name,
        )
    
    def _extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract common file metadata
        
        Returns: Dictionary with file stats
        """
        try:
            path = Path(file_path)
            stat = path.stat()
            
            return {
                'filename': path.name,
                'file_size_bytes': stat.st_size,
                'file_extension': path.suffix.lower(),
                'modified_time': stat.st_mtime,
            }
        except Exception:
            return {}


class ParserFactory:
    """
    Factory to get appropriate parser for file type
    
    Design Pattern: Factory Pattern
    """
    
    _parsers = {}
    
    @classmethod
    def register_parser(cls, file_type: str, parser_class: type):
        """Register parser for file type"""
        cls._parsers[file_type.lower()] = parser_class
    
    @classmethod
    def get_parser(cls, file_type: str) -> Optional[BaseParser]:
        """
        Get parser instance for file type
        
        Args:
            file_type: File type (e.g., 'pdf', 'docx', 'image')
        
        Returns:
            Parser instance or None if not found
        """
        parser_class = cls._parsers.get(file_type.lower())
        if parser_class:
            return parser_class()
        return None
    
    @classmethod
    def list_supported_types(cls) -> List[str]:
        """List all supported file types"""
        return list(cls._parsers.keys())
