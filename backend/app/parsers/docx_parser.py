"""
DOCX Parser - Production Grade

Strategy: Hybrid approach for maximum content extraction
1. python-docx - Primary, structured access to document elements
2. mammoth - Fallback, better HTML conversion
3. docx2txt - Fast text-only extraction

Features:
- Preserve formatting (headings, lists, tables)
- Extract images and embedded objects
- Metadata extraction
- Style preservation

Time Complexity: O(n) where n = document elements
"""
import time
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    import docx
    import docx2txt
    HAS_DOCX_LIBS = True
except ImportError:
    HAS_DOCX_LIBS = False

from app.parsers.base import BaseParser, ParseResult
from app.utils.text_utils import clean_text, extract_bullet_points


class DOCXParser(BaseParser):
    """
    Production-grade DOCX parser
    
    Features:
    - Structured element extraction (paragraphs, tables, headings)
    - Style and formatting preservation
    - Image extraction
    - Metadata extraction
    - Multi-method fallback for reliability
    """
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = {'.docx', '.doc'}
    
    def can_parse(self, file_path: Path) -> bool:
        """Check if file is a DOCX document."""
        return file_path.suffix.lower() in {'.docx', '.doc'}
    
    def parse(self, file_path: Path, **kwargs) -> ParseResult:
        """
        Parse DOCX document
        
        Options:
            extract_images: bool = True
            preserve_formatting: bool = True
            extract_tables: bool = True
        """
        if not HAS_DOCX_LIBS:
            return self._create_error_result("DOCX libraries not installed (python-docx, docx2txt)")
        
        start_time = time.time()
        
        # Convert to string for docx library compatibility
        file_path_str = str(file_path)
        
        # Validate file
        if not file_path.exists() or not file_path.is_file():
            return self._create_error_result(f"Invalid file: {file_path}")
        
        try:
            # Extract options
            extract_images = kwargs.get('extract_images', True)
            preserve_formatting = kwargs.get('preserve_formatting', True)
            extract_tables = kwargs.get('extract_tables', True)
            
            # Parse with python-docx (primary method)
            result = self._parse_with_python_docx(
                file_path_str,
                extract_images=extract_images,
                preserve_formatting=preserve_formatting,
                extract_tables=extract_tables
            )
            
            # If failed or empty, try docx2txt
            if not result.success or len(result.text) < 10:
                result = self._parse_with_docx2txt(file_path_str)
            
            # Calculate processing time
            result.processing_time_ms = (time.time() - start_time) * 1000
            
            return result
            
        except Exception as e:
            return self._create_error_result(f"DOCX parsing failed: {str(e)}")
    
    def _parse_with_python_docx(
        self,
        file_path: str,
        extract_images: bool = True,
        preserve_formatting: bool = True,
        extract_tables: bool = True
    ) -> ParseResult:
        """
        Parse DOCX using python-docx library
        
        Advantages:
        - Structured access to document elements
        - Preserve headings, lists, tables
        - Access to styles and formatting
        - Metadata extraction
        
        Time Complexity: O(n) where n = number of elements
        """
        try:
            doc = docx.Document(file_path)
            
            sections = []
            all_text = []
            tables_data = []
            images_data = []
            
            current_section = None
            
            # Process paragraphs
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                
                # Detect headings with proper regex pattern
                heading_match = re.match(r'Heading\s*(\d+)$', para.style.name)
                if heading_match:
                    # Save previous section
                    if current_section:
                        sections.append(current_section)
                    
                    # Start new section
                    level = int(heading_match.group(1))
                    current_section = {
                        'title': text,
                        'level': level,
                        'content': [],
                    }
                    # IMPORTANT: Add heading text to extracted text
                    all_text.append(text)
                else:
                    # Add to current section or main content
                    if preserve_formatting:
                        # Preserve bold, italic, etc.
                        formatted_text = self._get_formatted_text(para)
                        text = formatted_text
                    
                    if current_section:
                        current_section['content'].append(text)
                    
                    all_text.append(text)
            
            # Save last section
            if current_section:
                sections.append(current_section)
            
            # Extract tables
            if extract_tables:
                for table_idx, table in enumerate(doc.tables):
                    table_data = self._extract_table_data(table)
                    tables_data.append({
                        'table_index': table_idx,
                        'data': table_data,
                        'row_count': len(table_data),
                        'col_count': len(table_data[0]) if table_data else 0,
                    })
            
            # Extract images
            if extract_images:
                images_data = self._extract_images_info(doc)
            
            # Get metadata
            metadata = self._extract_docx_metadata(doc)
            metadata.update(self._extract_metadata(file_path))
            
            # Combine text
            combined_text = '\n\n'.join(all_text)
            cleaned_text = clean_text(combined_text, preserve_structure=True)
            
            return ParseResult(
                text=cleaned_text,
                sections=sections,
                tables=tables_data,
                images=images_data,
                metadata=metadata,
                success=True,
                parser_used='python-docx',
            )
            
        except Exception as e:
            return self._create_error_result(f"python-docx parsing failed: {str(e)}")
    
    def _parse_with_docx2txt(self, file_path: str) -> ParseResult:
        """
        Parse DOCX using docx2txt (fallback)
        
        Advantages:
        - Fast text extraction
        - Handles corrupted files better
        - Simple API
        
        Disadvantages:
        - No structure preservation
        - No formatting
        
        Time Complexity: O(n)
        """
        try:
            # Extract text (also extracts images to temp folder)
            text = docx2txt.process(file_path)
            
            if not text or len(text.strip()) < 10:
                return self._create_error_result("No text extracted from DOCX")
            
            # Clean text
            cleaned_text = clean_text(text, preserve_structure=True)
            
            # Get basic metadata
            metadata = self._extract_metadata(file_path)
            
            return ParseResult(
                text=cleaned_text,
                metadata=metadata,
                success=True,
                parser_used='docx2txt',
            )
            
        except Exception as e:
            return self._create_error_result(f"docx2txt parsing failed: {str(e)}")
    
    def _get_formatted_text(self, paragraph) -> str:
        """
        Extract text with formatting markers
        
        Preserves: bold, italic, underline
        Format: **bold** *italic* __underline__
        
        Handles hyperlinks: Includes runs inside w:hyperlink elements
        
        Time Complexity: O(n) where n = runs in paragraph
        """
        result = []
        
        # Iterate through all content including hyperlinks
        # paragraph.runs only returns direct children, excluding hyperlinks
        try:
            # Try to use iter_inner_content if available (newer python-docx)
            if hasattr(paragraph, 'iter_inner_content'):
                for item in paragraph.iter_inner_content():
                    if hasattr(item, 'runs'):
                        # It's a hyperlink, process its runs
                        for run in item.runs:
                            text = self._format_run_text(run)
                            result.append(text)
                    elif hasattr(item, 'text'):
                        # It's a run
                        text = self._format_run_text(item)
                        result.append(text)
            else:
                # Fallback: use standard paragraph.runs
                # This will miss hyperlinks but is better than nothing
                for run in paragraph.runs:
                    text = self._format_run_text(run)
                    result.append(text)
        except Exception:
            # Final fallback: plain text
            return paragraph.text
        
        return ''.join(result)
    
    def _format_run_text(self, run) -> str:
        """
        Format a single run with markers
        
        Args:
            run: A docx run object
            
        Returns:
            Formatted text string
        """
        text = run.text
        
        # Apply formatting markers
        if run.bold:
            text = f"**{text}**"
        if run.italic:
            text = f"*{text}*"
        if run.underline:
            text = f"__{text}__"
        
        return text
    
    def _extract_table_data(self, table) -> List[List[str]]:
        """
        Extract table as 2D array
        
        Returns: List of rows, each row is list of cell values
        
        Time Complexity: O(rows * cols)
        """
        data = []
        
        for row in table.rows:
            row_data = []
            for cell in row.cells:
                # Extract text from all paragraphs in cell
                cell_text = '\n'.join(p.text for p in cell.paragraphs if p.text.strip())
                row_data.append(cell_text.strip())
            data.append(row_data)
        
        return data
    
    def _extract_images_info(self, doc) -> List[Dict[str, Any]]:
        """
        Extract information about embedded images
        
        Note: Actual image extraction requires zip manipulation
        
        Returns: List of image metadata
        """
        images = []
        
        try:
            # DOCX is a zip file, can extract images from word/media/
            # For now, just count images in paragraphs
            image_count = 0
            
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    images.append({
                        'index': image_count,
                        'type': rel.target_ref.split('/')[-1],
                    })
                    image_count += 1
        except:
            pass
        
        return images
    
    def _extract_docx_metadata(self, doc) -> Dict[str, Any]:
        """
        Extract document metadata from core properties
        
        Returns: Dictionary with title, author, created, etc.
        """
        try:
            props = doc.core_properties
            
            metadata = {
                'title': props.title or '',
                'author': props.author or '',
                'subject': props.subject or '',
                'keywords': props.keywords or '',
                'created': str(props.created) if props.created else '',
                'modified': str(props.modified) if props.modified else '',
                'last_modified_by': props.last_modified_by or '',
                'revision': props.revision,
                'category': props.category or '',
            }
            
            # Remove empty values
            return {k: v for k, v in metadata.items() if v}
            
        except Exception:
            return {}
    
    def extract_styles(self, file_path: str) -> List[str]:
        """
        Extract all styles used in document
        
        Use case: Style analysis, theme detection
        
        Returns: List of style names
        """
        try:
            doc = docx.Document(file_path)
            styles = set()
            
            for para in doc.paragraphs:
                if para.style:
                    styles.add(para.style.name)
            
            return sorted(list(styles))
            
        except Exception:
            return []

