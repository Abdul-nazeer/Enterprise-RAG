"""
Document Parsers Package

Production-grade parsers using state-of-the-art tools:
- PDF: PyMuPDF + pdfplumber (hybrid approach)
- Images: PaddleOCR (better than Tesseract)
- DOCX: python-docx + mammoth
- Code: AST-based parsing
- Mermaid: Specialized syntax parser

Design Pattern: Strategy Pattern
- Each parser implements parse() method
- Returns structured ParseResult
- Handles errors gracefully with fallbacks
"""
from app.parsers.base import BaseParser, ParseResult
from app.parsers.pdf_parser import PDFParser
from app.parsers.image_parser import ImageParser
from app.parsers.docx_parser import DOCXParser
from app.parsers.text_parser import TextParser
from app.parsers.code_parser import CodeParser
from app.parsers.mermaid_parser import MermaidParser

__all__ = [
    "BaseParser",
    "ParseResult",
    "PDFParser",
    "ImageParser",
    "DOCXParser",
    "TextParser",
    "CodeParser",
    "MermaidParser",
]
