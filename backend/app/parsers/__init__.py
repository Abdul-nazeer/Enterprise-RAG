"""
Document Parsers Package

Production-grade parsers for multiple document types:
- PDF: PyMuPDF + pdfplumber hybrid
- Images: PaddleOCR + EasyOCR fallback
- DOCX: python-docx + mammoth + docx2txt
- Text/Markdown: Encoding detection + structure preservation
- Code: AST-based parsing for Python, JS, Java, C++, etc.
- Mermaid: Diagram syntax parsing
"""

from app.parsers.base import BaseParser, ParseResult, ParserFactory
from app.parsers.pdf_parser import PDFParser
from app.parsers.image_parser import ImageParser
from app.parsers.docx_parser import DOCXParser
from app.parsers.text_parser import TextParser
from app.parsers.code_parser import CodeParser
from app.parsers.mermaid_parser import MermaidParser

__all__ = [
    'BaseParser',
    'ParseResult',
    'ParserFactory',
    'PDFParser',
    'ImageParser',
    'DOCXParser',
    'TextParser',
    'CodeParser',
    'MermaidParser',
]
