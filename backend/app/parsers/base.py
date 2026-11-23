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
    def parse(self, file_path: Path, **kwargs) -> ParseResult:
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
    
    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """
        Check if this parser can handle the given file
        
        Args:
            file_path: Path to check
        
        Returns:
            True if parser can handle this file
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
    
    Design Pattern: Factory Pattern with auto-registration
    """
    
    _parsers: List[BaseParser] = []
    _initialized: bool = False
    
    @classmethod
    def _initialize_parsers(cls) -> None:
        """Initialize and register all available parsers"""
        if cls._initialized:
            return
        
        # Import parsers here to avoid circular imports
        from app.parsers.pdf_parser import PDFParser
        from app.parsers.docx_parser import DOCXParser
        from app.parsers.text_parser import TextParser
        from app.parsers.code_parser import CodeParser
        from app.parsers.mermaid_parser import MermaidParser
        
        # Try to import ImageParser (requires paddleocr/easyocr)
        try:
            from app.parsers.image_parser import ImageParser
            has_image_parser = True
        except ImportError:
            has_image_parser = False
        
        # Register parsers in order of specificity (most specific first)
        cls.register_parser(MermaidParser())  # Most specific
        cls.register_parser(CodeParser())
        cls.register_parser(PDFParser())
        cls.register_parser(DOCXParser())
        if has_image_parser:
            cls.register_parser(ImageParser())
        cls.register_parser(TextParser())  # Most generic (fallback)
        
        cls._initialized = True
    
    @classmethod
    def register_parser(cls, parser: BaseParser) -> None:
        """Register a parser instance"""
        cls._parsers.append(parser)
    
    @classmethod
    def get_parser(cls, file_path: Path) -> Optional[BaseParser]:
        """
        Get appropriate parser for file
        
        Args:
            file_path: Path to file
        
        Returns:
            Parser instance that can handle the file, or None
        """
        cls._initialize_parsers()
        
        for parser in cls._parsers:
            if parser.can_parse(file_path):
                return parser
        return None
    
    @classmethod
    def parse_file(cls, file_path: Path) -> ParseResult:
        """
        Parse file using appropriate parser
        
        Args:
            file_path: Path to file
        
        Returns:
            ParseResult with content and metadata
        
        Raises:
            ParsingException if no parser found
        """
        from app.core.exceptions import ParsingException
        
        parser = cls.get_parser(file_path)
        if parser is None:
            raise ParsingException(
                f"No parser found for file: {file_path}",
                parser_type="unknown",
                file_path=str(file_path)
            )
        return parser.parse(file_path)
    
    @classmethod
    def get_supported_extensions(cls) -> set:
        """Get all supported file extensions across all parsers"""
        cls._initialize_parsers()
        
        extensions = set()
        for parser in cls._parsers:
            if hasattr(parser, 'supported_extensions'):
                extensions.update(parser.supported_extensions)
            elif hasattr(parser, 'get_supported_extensions'):
                extensions.update(parser.get_supported_extensions())
        return extensions
    
    @classmethod
    def list_supported_types(cls) -> List[str]:
        """List all supported file types"""
        return sorted(list(cls.get_supported_extensions()))
