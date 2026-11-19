"""
PDF Parser - Production Grade

Strategy: Hybrid approach using multiple libraries
1. PyMuPDF (fitz) - Primary, fast text extraction
2. pdfplumber - Fallback, better for tables and complex layouts
3. Unstructured - Advanced parsing for scanned PDFs

Algorithm:
- Try PyMuPDF first (fastest)
- If text quality low, try pdfplumber
- If still poor, treat as scanned (use OCR)
- Extract tables separately with pdfplumber

Time Complexity: O(n) where n = number of pages
"""
import time
import fitz  # PyMuPDF
import pdfplumber
from typing import List, Dict, Any, Optional
from pathlib import Path

from app.parsers.base import BaseParser, ParseResult
from app.utils.text_utils import clean_text


class PDFParser(BaseParser):
    """
    Production-grade PDF parser with hybrid approach
    
    Features:
    - Multi-library fallback for reliability
    - Table extraction
    - Image extraction
    - Metadata extraction
    - Scanned PDF detection
    """
    
    def __init__(self):
        super().__init__()
        self.min_text_threshold = 100  # Min chars to consider valid extraction
    
    def parse(self, file_path: str, **kwargs) -> ParseResult:
        """
        Parse PDF document
        
        Options:
            extract_tables: bool = True
            extract_images: bool = False
            ocr_scanned: bool = True
        """
        start_time = time.time()
        
        # Validate file
        if not self.validate_file(file_path):
            return self._create_error_result(f"Invalid file: {file_path}")
        
        try:
            # Extract options
            extract_tables = kwargs.get('extract_tables', True)
            extract_images = kwargs.get('extract_images', False)
            ocr_scanned = kwargs.get('ocr_scanned', True)
            
            # Try PyMuPDF first (fastest)
            result = self._parse_with_pymupdf(
                file_path,
                extract_images=extract_images
            )
            
            # Check if extraction quality is good
            if len(result.text) < self.min_text_threshold:
                # Try pdfplumber (better for complex layouts)
                result = self._parse_with_pdfplumber(file_path)
                
                # Still poor quality? Might be scanned
                if len(result.text) < self.min_text_threshold and ocr_scanned:
                    result.metadata['is_scanned'] = True
                    result.metadata['needs_ocr'] = True
            
            # Extract tables (pdfplumber is best for this)
            if extract_tables and result.success:
                tables = self._extract_tables(file_path)
                result.tables = tables
                result.metadata['has_tables'] = len(tables) > 0
            
            # Calculate processing time
            result.processing_time_ms = (time.time() - start_time) * 1000
            
            return result
            
        except Exception as e:
            return self._create_error_result(f"PDF parsing failed: {str(e)}")
    
    def _parse_with_pymupdf(
        self,
        file_path: str,
        extract_images: bool = False
    ) -> ParseResult:
        """
        Parse PDF using PyMuPDF (fitz)
        
        Advantages:
        - Fast extraction
        - Good for text-based PDFs
        - Built-in image extraction
        
        Time Complexity: O(n) where n = pages
        """
        try:
            doc = fitz.open(file_path)
            
            pages_data = []
            all_text = []
            images_data = []
            
            for page_num, page in enumerate(doc):
                # Extract text
                text = page.get_text("text")
                clean_page_text = clean_text(text, preserve_structure=True)
                
                # Store page data
                page_data = {
                    'page_number': page_num + 1,
                    'text': clean_page_text,
                    'char_count': len(clean_page_text),
                    'has_images': len(page.get_images()) > 0,
                }
                pages_data.append(page_data)
                all_text.append(clean_page_text)
                
                # Extract images if requested
                if extract_images:
                    images = page.get_images()
                    for img_index, img in enumerate(images):
                        images_data.append({
                            'page': page_num + 1,
                            'index': img_index,
                            'xref': img[0],
                        })
            
            # Get document metadata
            metadata = self._extract_pdf_metadata(doc)
            metadata.update(self._extract_metadata(file_path))
            
            doc.close()
            
            return ParseResult(
                text='\n\n'.join(all_text),
                pages=pages_data,
                images=images_data,
                metadata=metadata,
                success=True,
                parser_used='pymupdf',
            )
            
        except Exception as e:
            return self._create_error_result(f"PyMuPDF parsing failed: {str(e)}")
    
    def _parse_with_pdfplumber(self, file_path: str) -> ParseResult:
        """
        Parse PDF using pdfplumber
        
        Advantages:
        - Better for complex layouts
        - Excellent table extraction
        - Good for forms
        
        Time Complexity: O(n) where n = pages
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                pages_data = []
                all_text = []
                
                for page in pdf.pages:
                    # Extract text
                    text = page.extract_text() or ""
                    clean_page_text = clean_text(text, preserve_structure=True)
                    
                    # Store page data
                    page_data = {
                        'page_number': page.page_number,
                        'text': clean_page_text,
                        'char_count': len(clean_page_text),
                        'width': page.width,
                        'height': page.height,
                    }
                    pages_data.append(page_data)
                    all_text.append(clean_page_text)
                
                # Get metadata
                metadata = pdf.metadata or {}
                metadata.update(self._extract_metadata(file_path))
                
                return ParseResult(
                    text='\n\n'.join(all_text),
                    pages=pages_data,
                    metadata=metadata,
                    success=True,
                    parser_used='pdfplumber',
                )
                
        except Exception as e:
            return self._create_error_result(f"pdfplumber parsing failed: {str(e)}")
    
    def _extract_tables(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract tables from PDF using pdfplumber
        
        Returns list of tables with:
        - page_number
        - table_index
        - data (2D array)
        - row_count, col_count
        
        Time Complexity: O(n*m) where n=pages, m=tables per page
        """
        tables = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    
                    for table_index, table_data in enumerate(page_tables):
                        if table_data:
                            tables.append({
                                'page_number': page.page_number,
                                'table_index': table_index,
                                'data': table_data,
                                'row_count': len(table_data),
                                'col_count': len(table_data[0]) if table_data else 0,
                            })
        except Exception as e:
            # Non-fatal: tables are optional
            pass
        
        return tables
    
    def _extract_pdf_metadata(self, doc: fitz.Document) -> Dict[str, Any]:
        """
        Extract PDF metadata from fitz document
        
        Returns: Dictionary with title, author, subject, etc.
        """
        try:
            metadata = {
                'title': doc.metadata.get('title', ''),
                'author': doc.metadata.get('author', ''),
                'subject': doc.metadata.get('subject', ''),
                'keywords': doc.metadata.get('keywords', ''),
                'creator': doc.metadata.get('creator', ''),
                'producer': doc.metadata.get('producer', ''),
                'creation_date': doc.metadata.get('creationDate', ''),
                'modification_date': doc.metadata.get('modDate', ''),
                'page_count': doc.page_count,
                'is_encrypted': doc.is_encrypted,
            }
            return {k: v for k, v in metadata.items() if v}  # Remove empty values
        except Exception:
            return {}
    
    def is_scanned_pdf(self, file_path: str) -> bool:
        """
        Detect if PDF is scanned (image-based) vs text-based
        
        Algorithm:
        - Extract text from first 3 pages
        - If text < 100 chars but has images, likely scanned
        
        Time Complexity: O(1) - only checks first few pages
        """
        try:
            doc = fitz.open(file_path)
            pages_to_check = min(3, doc.page_count)
            
            total_text = 0
            total_images = 0
            
            for page_num in range(pages_to_check):
                page = doc[page_num]
                text = page.get_text("text")
                total_text += len(text.strip())
                total_images += len(page.get_images())
            
            doc.close()
            
            # Heuristic: If < 100 chars but has images, it's scanned
            return total_text < 100 and total_images > 0
            
        except Exception:
            return False


# Register parser
from app.parsers.base import ParserFactory
ParserFactory.register_parser('pdf', PDFParser)
