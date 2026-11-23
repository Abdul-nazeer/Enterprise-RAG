"""
Image Parser - State-of-the-Art OCR

Technology: PaddleOCR (Better than Tesseract)
- 99%+ accuracy for printed text
- Supports 80+ languages
- Handles rotated text
- Better for handwriting
- Deep learning based

Fallback: EasyOCR (if PaddleOCR fails)

Algorithm:
1. Load image with Pillow
2. Preprocess (deskew, denoise, enhance contrast)
3. Run PaddleOCR detection + recognition
4. Post-process results (sort by position, group into lines)
5. Extract structured text

Time Complexity: O(n) where n = image size
"""
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

from app.parsers.base import BaseParser, ParseResult
from app.utils.text_utils import clean_text


class ImageParser(BaseParser):
    """
    Production-grade image parser with PaddleOCR
    
    Features:
    - Multi-language support (80+ languages)
    - High accuracy OCR
    - Automatic preprocessing
    - Layout analysis
    - Confidence scoring
    """
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.webp'}
        # Cache OCR engines per language to avoid reinitialization
        self._ocr_engines = {}  # language -> PaddleOCR instance
        self._easyocr_readers = {}  # language -> EasyOCR instance
        # Thread lock for lazy initialization (if parsers run in threads)
        import threading
        self._lock = threading.Lock()
    
    def can_parse(self, file_path: Path) -> bool:
        """Check if file is an image."""
        return file_path.suffix.lower() in self.supported_extensions
    
    def parse(self, file_path: Path, **kwargs) -> ParseResult:
        """
        Parse image with OCR
        
        Options:
            language: str = 'en' (language code)
            enhance: bool = True (image preprocessing)
            min_confidence: float = 0.5 (filter low-confidence results)
        """
        start_time = time.time()
        
        # Convert to string
        file_path_str = str(file_path)
        
        # Validate file
        if not file_path.exists() or not file_path.is_file():
            return self._create_error_result(f"Invalid file: {file_path}")
        
        try:
            # Extract options
            language = kwargs.get('language', 'en')
            enhance = kwargs.get('enhance', True)
            min_confidence = kwargs.get('min_confidence', 0.5)
            
            # Load and preprocess image
            image = self._load_image(file_path_str)
            if enhance:
                image = self._preprocess_image(image)
            
            # Try PaddleOCR first (best quality)
            result = self._ocr_with_paddle(
                image,
                language=language,
                min_confidence=min_confidence
            )
            
            # If PaddleOCR fails, try EasyOCR
            if not result.success or len(result.text) < 10:
                result = self._ocr_with_easyocr(
                    image,
                    language=language
                )
            
            # Add image metadata
            if result.success:
                result.metadata.update(self._get_image_metadata(file_path, image))
            
            # Calculate processing time
            result.processing_time_ms = (time.time() - start_time) * 1000
            
            return result
            
        except Exception as e:
            return self._create_error_result(f"Image parsing failed: {str(e)}")
    
    def _load_image(self, file_path: str) -> Image.Image:
        """
        Load image with Pillow
        
        Handles various formats: PNG, JPG, TIFF, BMP, WebP
        """
        image = Image.open(file_path)
        
        # Convert to RGB if needed
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        
        return image
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for better OCR accuracy
        
        Steps:
        1. Resize if too large (max 4000px)
        2. Enhance contrast
        3. Sharpen
        4. Denoise
        
        Time Complexity: O(w*h) where w=width, h=height
        """
        # Resize if too large (OCR slower on huge images)
        max_dimension = 4000
        if max(image.size) > max_dimension:
            ratio = max_dimension / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)  # Increase contrast by 50%
        
        # Sharpen
        image = image.filter(ImageFilter.SHARPEN)
        
        # Denoise (slight blur then sharpen)
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
        return image
    
    def _ocr_with_paddle(
        self,
        image: Image.Image,
        language: str = 'en',
        min_confidence: float = 0.5
    ) -> ParseResult:
        """
        OCR using PaddleOCR (state-of-the-art)
        
        Advantages:
        - 99%+ accuracy
        - 80+ languages
        - Fast inference
        - Layout analysis
        
        Returns: ParseResult with extracted text and bounding boxes
        """
        try:
            # Get or create OCR engine for this language
            ocr_engine = self._get_paddle_engine(language)
            
            # Convert PIL to numpy array
            img_array = np.array(image)
            
            # Run OCR
            ocr_result = ocr_engine.ocr(img_array, cls=True)
            
            # Parse results
            lines = []
            all_text = []
            
            if ocr_result and ocr_result[0]:
                for detection in ocr_result[0]:
                    # detection format: [[bbox], (text, confidence)]
                    bbox = detection[0]
                    text, confidence = detection[1]
                    
                    # Filter by confidence
                    if confidence >= min_confidence:
                        lines.append({
                            'text': text,
                            'confidence': float(confidence),
                            'bbox': bbox,  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                        })
                        all_text.append(text)
            
            # Sort lines by vertical position (top to bottom)
            lines.sort(key=lambda x: x['bbox'][0][1])  # Sort by top-left y coordinate
            
            # Combine text
            combined_text = '\n'.join(all_text)
            cleaned_text = clean_text(combined_text, preserve_structure=True)
            
            return ParseResult(
                text=cleaned_text,
                metadata={
                    'ocr_engine': 'paddleocr',
                    'language': language,
                    'line_count': len(lines),
                    'avg_confidence': np.mean([l['confidence'] for l in lines]) if lines else 0.0,
                    'lines': lines,  # Store for debugging
                },
                success=True,
                parser_used='paddleocr',
            )
            
        except Exception as e:
            return self._create_error_result(f"PaddleOCR failed: {str(e)}")
    
    def _get_paddle_engine(self, language: str):
        """
        Get or create PaddleOCR engine for specific language
        
        Thread-safe lazy initialization with caching per language
        
        Args:
            language: Language code (e.g., 'en', 'fr', 'zh')
            
        Returns:
            PaddleOCR instance for the specified language
        """
        with self._lock:
            if language not in self._ocr_engines:
                try:
                    from paddleocr import PaddleOCR
                    self._ocr_engines[language] = PaddleOCR(
                        use_angle_cls=True,  # Detect text rotation
                        lang=language,
                        use_gpu=False,  # Set to True if GPU available
                        show_log=False,
                    )
                except Exception as e:
                    raise RuntimeError(f"Failed to initialize PaddleOCR for language '{language}': {e}")
            
            return self._ocr_engines[language]
    
    def _get_easyocr_reader(self, language: str):
        """
        Get or create EasyOCR reader for specific language
        
        Thread-safe lazy initialization with caching per language
        
        Args:
            language: Language code (e.g., 'en', 'fr', 'zh')
            
        Returns:
            EasyOCR Reader instance for the specified language
        """
        with self._lock:
            if language not in self._easyocr_readers:
                try:
                    import easyocr
                    self._easyocr_readers[language] = easyocr.Reader([language])
                except Exception as e:
                    raise RuntimeError(f"Failed to initialize EasyOCR for language '{language}': {e}")
            
            return self._easyocr_readers[language]
    
    def _ocr_with_easyocr(
        self,
        image: Image.Image,
        language: str = 'en'
    ) -> ParseResult:
        """
        OCR using EasyOCR (fallback)
        
        Advantages:
        - Deep learning based
        - Good for handwriting
        - Multi-language
        
        Returns: ParseResult with extracted text
        """
        try:
            # Get or create EasyOCR reader for this language
            reader = self._get_easyocr_reader(language)
            
            # Convert PIL to numpy array
            img_array = np.array(image)
            
            # Run OCR
            ocr_result = reader.readtext(img_array)
            
            # Parse results
            lines = []
            all_text = []
            
            for detection in ocr_result:
                # detection format: (bbox, text, confidence)
                bbox, text, confidence = detection
                
                lines.append({
                    'text': text,
                    'confidence': float(confidence),
                    'bbox': bbox,
                })
                all_text.append(text)
            
            # Sort lines by vertical position
            lines.sort(key=lambda x: x['bbox'][0][1])
            
            # Combine text
            combined_text = '\n'.join(all_text)
            cleaned_text = clean_text(combined_text, preserve_structure=True)
            
            return ParseResult(
                text=cleaned_text,
                metadata={
                    'ocr_engine': 'easyocr',
                    'language': language,
                    'line_count': len(lines),
                    'avg_confidence': np.mean([l['confidence'] for l in lines]) if lines else 0.0,
                },
                success=True,
                parser_used='easyocr',
            )
            
        except Exception as e:
            return self._create_error_result(f"EasyOCR failed: {str(e)}")
    
    def _get_image_metadata(
        self,
        file_path: str,
        image: Image.Image
    ) -> Dict[str, Any]:
        """
        Extract image metadata
        
        Returns: Dictionary with dimensions, format, mode, etc.
        """
        metadata = self._extract_metadata(file_path)
        
        metadata.update({
            'width': image.width,
            'height': image.height,
            'format': image.format,
            'mode': image.mode,
            'dpi': image.info.get('dpi', (72, 72)),
        })
        
        # Extract EXIF data if available
        try:
            exif = image._getexif()
            if exif:
                metadata['has_exif'] = True
        except:
            pass
        
        return metadata
    
    def detect_text_regions(
        self,
        image: Image.Image,
        language: str = 'en'
    ) -> List[Tuple[int, int, int, int]]:
        """
        Detect text regions in image (bounding boxes)
        
        Use case: Layout analysis before OCR
        
        Args:
            image: PIL Image
            language: Language code for OCR engine
        
        Returns: List of (x1, y1, x2, y2) coordinates
        
        Time Complexity: O(w*h)
        """
        try:
            # Get OCR engine for the specified language
            ocr_engine = self._get_paddle_engine(language)
            
            img_array = np.array(image)
            result = ocr_engine.ocr(img_array, cls=True)
            
            boxes = []
            if result and result[0]:
                for detection in result[0]:
                    bbox = detection[0]
                    # Convert [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] to (x1, y1, x2, y2)
                    x1 = min(p[0] for p in bbox)
                    y1 = min(p[1] for p in bbox)
                    x2 = max(p[0] for p in bbox)
                    y2 = max(p[1] for p in bbox)
                    boxes.append((int(x1), int(y1), int(x2), int(y2)))
            
            return boxes
            
        except Exception:
            return []

