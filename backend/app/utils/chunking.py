"""
Text Chunking Strategies for RAG

Design Decision: Multiple chunking strategies for different use cases
- Fixed-size: Simple, consistent chunks
- Sentence-based: Semantic boundaries
- Paragraph-based: Natural document structure
- Recursive: Hierarchical with overlap
- Semantic: Similarity-based (future: use embeddings)

Why chunking matters:
- Too small: Lose context
- Too large: Exceed context window, poor retrieval
- Optimal: 256-512 tokens (balance context vs precision)

Algorithm Selection:
- Documents: Paragraph-based
- Code: Function/class-based
- Chat: Fixed-size with overlap
"""
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.utils.text_utils import (
    split_into_sentences,
    count_tokens_approx,
    count_words,
)


@dataclass
class TextChunk:
    """
    Data class for text chunks
    
    Design: Rich metadata for better retrieval
    """
    content: str
    chunk_index: int
    token_count: int
    word_count: int
    metadata: Dict[str, Any]
    
    def to_dict(self) -> dict:
        return {
            'content': self.content,
            'chunk_index': self.chunk_index,
            'token_count': self.token_count,
            'word_count': self.word_count,
            'metadata': self.metadata,
        }


class ChunkingStrategy:
    """Base class for chunking strategies"""
    
    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[TextChunk]:
        """
        Chunk text into smaller pieces
        
        Args:
            text: Input text
            metadata: Additional metadata to attach to chunks
        
        Returns:
            List of TextChunk objects
        """
        raise NotImplementedError


class FixedSizeChunker(ChunkingStrategy):
    """
    Fixed-size chunking with overlap
    
    Algorithm:
    1. Split text into chunks of fixed size
    2. Add overlap between chunks for context continuity
    3. Don't break mid-sentence if possible
    
    Use case: General-purpose, simple to implement
    
    Time Complexity: O(n) where n = text length
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 50,
        preserve_sentences: bool = True
    ):
        """
        Args:
            chunk_size: Target tokens per chunk
            overlap: Token overlap between chunks
            preserve_sentences: Don't break mid-sentence
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.preserve_sentences = preserve_sentences
    
    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[TextChunk]:
        """
        Chunk text with fixed size and overlap
        
        Algorithm:
        - Sliding window of size chunk_size
        - Step size = chunk_size - overlap
        - Adjust boundaries to sentence ends if preserve_sentences=True
        """
        if not text or not text.strip():
            return []
        
        metadata = metadata or {}
        chunks = []
        
        # Approximate: 4 chars ≈ 1 token
        char_per_token = 4
        chunk_char_size = self.chunk_size * char_per_token
        overlap_char_size = self.overlap * char_per_token
        
        start = 0
        chunk_index = 0
        
        while start < len(text):
            # Calculate end position
            end = start + chunk_char_size
            
            # Don't exceed text length
            end = min(end, len(text))
            
            # Extract chunk
            chunk_text = text[start:end]
            
            # Preserve sentence boundaries
            if self.preserve_sentences and end < len(text):
                # Find last sentence boundary in chunk
                last_period = chunk_text.rfind('. ')
                last_newline = chunk_text.rfind('\n')
                last_boundary = max(last_period, last_newline)
                
                if last_boundary > len(chunk_text) // 2:  # At least halfway through
                    chunk_text = chunk_text[:last_boundary + 1]
                    end = start + last_boundary + 1
            
            # Create chunk
            chunk_text = chunk_text.strip()
            if chunk_text:
                chunk = TextChunk(
                    content=chunk_text,
                    chunk_index=chunk_index,
                    token_count=count_tokens_approx(chunk_text),
                    word_count=count_words(chunk_text),
                    metadata={
                        **metadata,
                        'start_char': start,
                        'end_char': end,
                        'chunking_strategy': 'fixed_size',
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
            
            # Move to next chunk (with overlap)
            start = end - overlap_char_size
            
            # Ensure progress
            if start >= end:
                start = end
        
        return chunks


class SentenceChunker(ChunkingStrategy):
    """
    Sentence-based chunking
    
    Algorithm:
    1. Split text into sentences
    2. Group sentences until target size reached
    3. Create chunks with sentence boundaries
    
    Advantages:
    - Preserves semantic units
    - No mid-sentence breaks
    - Better for Q&A
    
    Time Complexity: O(n)
    """
    
    def __init__(
        self,
        target_tokens: int = 384,
        min_sentences: int = 1,
        max_sentences: int = 10
    ):
        self.target_tokens = target_tokens
        self.min_sentences = min_sentences
        self.max_sentences = max_sentences
    
    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[TextChunk]:
        """
        Chunk text by grouping sentences
        """
        if not text or not text.strip():
            return []
        
        metadata = metadata or {}
        chunks = []
        
        # Split into sentences
        sentences = split_into_sentences(text)
        if not sentences:
            return []
        
        current_chunk = []
        current_tokens = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_tokens = count_tokens_approx(sentence)
            
            # Check if adding sentence exceeds target
            if current_tokens + sentence_tokens > self.target_tokens and len(current_chunk) >= self.min_sentences:
                # Save current chunk
                chunk_text = ' '.join(current_chunk)
                chunk = TextChunk(
                    content=chunk_text,
                    chunk_index=chunk_index,
                    token_count=current_tokens,
                    word_count=count_words(chunk_text),
                    metadata={
                        **metadata,
                        'sentence_count': len(current_chunk),
                        'chunking_strategy': 'sentence',
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
                
                # Start new chunk
                current_chunk = [sentence]
                current_tokens = sentence_tokens
            else:
                # Add to current chunk
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
            
            # Enforce max sentences
            if len(current_chunk) >= self.max_sentences:
                chunk_text = ' '.join(current_chunk)
                chunk = TextChunk(
                    content=chunk_text,
                    chunk_index=chunk_index,
                    token_count=current_tokens,
                    word_count=count_words(chunk_text),
                    metadata={
                        **metadata,
                        'sentence_count': len(current_chunk),
                        'chunking_strategy': 'sentence',
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
                
                current_chunk = []
                current_tokens = 0
        
        # Add remaining sentences
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk = TextChunk(
                content=chunk_text,
                chunk_index=chunk_index,
                token_count=current_tokens,
                word_count=count_words(chunk_text),
                metadata={
                    **metadata,
                    'sentence_count': len(current_chunk),
                    'chunking_strategy': 'sentence',
                }
            )
            chunks.append(chunk)
        
        return chunks


class ParagraphChunker(ChunkingStrategy):
    """
    Paragraph-based chunking
    
    Algorithm:
    1. Split text by double newlines (paragraphs)
    2. Group paragraphs until target size
    3. Preserve paragraph structure
    
    Best for: Documents, articles, books
    
    Time Complexity: O(n)
    """
    
    def __init__(self, target_tokens: int = 512):
        self.target_tokens = target_tokens
    
    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[TextChunk]:
        """
        Chunk text by paragraphs
        """
        if not text or not text.strip():
            return []
        
        metadata = metadata or {}
        chunks = []
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if not paragraphs:
            return []
        
        current_chunk = []
        current_tokens = 0
        chunk_index = 0
        
        for para in paragraphs:
            para_tokens = count_tokens_approx(para)
            
            # Single paragraph too large? Split it
            if para_tokens > self.target_tokens * 1.5:
                # Save current chunk if any
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunk = TextChunk(
                        content=chunk_text,
                        chunk_index=chunk_index,
                        token_count=current_tokens,
                        word_count=count_words(chunk_text),
                        metadata={
                            **metadata,
                            'paragraph_count': len(current_chunk),
                            'chunking_strategy': 'paragraph',
                        }
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                    current_chunk = []
                    current_tokens = 0
                
                # Split large paragraph with sentence chunker
                sentence_chunker = SentenceChunker(target_tokens=self.target_tokens)
                para_chunks = sentence_chunker.chunk(para, metadata)
                for pc in para_chunks:
                    pc.chunk_index = chunk_index
                    chunks.append(pc)
                    chunk_index += 1
                
                continue
            
            # Check if adding paragraph exceeds target
            if current_tokens + para_tokens > self.target_tokens and current_chunk:
                # Save current chunk
                chunk_text = '\n\n'.join(current_chunk)
                chunk = TextChunk(
                    content=chunk_text,
                    chunk_index=chunk_index,
                    token_count=current_tokens,
                    word_count=count_words(chunk_text),
                    metadata={
                        **metadata,
                        'paragraph_count': len(current_chunk),
                        'chunking_strategy': 'paragraph',
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
                
                # Start new chunk
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                # Add to current chunk
                current_chunk.append(para)
                current_tokens += para_tokens
        
        # Add remaining paragraphs
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunk = TextChunk(
                content=chunk_text,
                chunk_index=chunk_index,
                token_count=current_tokens,
                word_count=count_words(chunk_text),
                metadata={
                    **metadata,
                    'paragraph_count': len(current_chunk),
                    'chunking_strategy': 'paragraph',
                }
            )
            chunks.append(chunk)
        
        return chunks


class CodeChunker(ChunkingStrategy):
    """
    Code-specific chunking
    
    Algorithm:
    1. Detect functions/classes/methods
    2. Keep complete code units together
    3. Add overlap for context (imports, class definitions)
    
    Pattern recognition:
    - Python: def, class, @decorator
    - JavaScript: function, class, arrow functions
    - Java/C++: public/private class, methods
    
    Time Complexity: O(n)
    """
    
    def __init__(self, target_tokens: int = 512):
        self.target_tokens = target_tokens
    
    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[TextChunk]:
        """
        Chunk code by logical units
        """
        if not text or not text.strip():
            return []
        
        metadata = metadata or {}
        
        # Detect language (simplified)
        language = metadata.get('language', self._detect_language(text))
        
        # Try to split by functions/classes
        units = self._split_code_units(text, language)
        
        # If no units detected, use fixed-size chunker
        if not units or len(units) == 1:
            fixed_chunker = FixedSizeChunker(
                chunk_size=self.target_tokens,
                overlap=50,
                preserve_sentences=False
            )
            return fixed_chunker.chunk(text, metadata)
        
        # Group units into chunks
        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_index = 0
        
        for unit in units:
            unit_tokens = count_tokens_approx(unit)
            
            if current_tokens + unit_tokens > self.target_tokens and current_chunk:
                # Save current chunk
                chunk_text = '\n\n'.join(current_chunk)
                chunk = TextChunk(
                    content=chunk_text,
                    chunk_index=chunk_index,
                    token_count=current_tokens,
                    word_count=count_words(chunk_text),
                    metadata={
                        **metadata,
                        'code_units': len(current_chunk),
                        'chunking_strategy': 'code',
                        'language': language,
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
                
                current_chunk = [unit]
                current_tokens = unit_tokens
            else:
                current_chunk.append(unit)
                current_tokens += unit_tokens
        
        # Add remaining units
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunk = TextChunk(
                content=chunk_text,
                chunk_index=chunk_index,
                token_count=current_tokens,
                word_count=count_words(chunk_text),
                metadata={
                    **metadata,
                    'code_units': len(current_chunk),
                    'chunking_strategy': 'code',
                    'language': language,
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def _detect_language(self, code: str) -> str:
        """Simple language detection"""
        if 'def ' in code or 'import ' in code:
            return 'python'
        elif 'function ' in code or 'const ' in code or 'let ' in code:
            return 'javascript'
        elif 'public class' in code or 'private class' in code:
            return 'java'
        elif '#include' in code:
            return 'cpp'
        return 'unknown'
    
    def _split_code_units(self, code: str, language: str) -> List[str]:
        """Split code into logical units (functions, classes)"""
        # Python: split by def and class
        if language == 'python':
            pattern = r'(^(?:def |class |@\w+\s+def |@\w+\s+class ).+?)(?=^(?:def |class |@\w+)|$)'
            units = re.findall(pattern, code, re.MULTILINE | re.DOTALL)
            if units:
                return units
        
        # JavaScript: split by function and class
        elif language == 'javascript':
            pattern = r'((?:function |class |const \w+ = (?:function|\()|\w+\s*=\s*\().+?)(?=(?:function |class |const \w+ = |$))'
            units = re.findall(pattern, code, re.DOTALL)
            if units:
                return units
        
        # Fallback: split by double newlines
        return [u.strip() for u in code.split('\n\n') if u.strip()]


def get_chunker(strategy: str, **kwargs) -> ChunkingStrategy:
    """
    Factory function to get chunker by strategy name
    
    Args:
        strategy: 'fixed', 'sentence', 'paragraph', 'code'
        **kwargs: Strategy-specific parameters
    
    Returns:
        ChunkingStrategy instance
    """
    strategies = {
        'fixed': FixedSizeChunker,
        'sentence': SentenceChunker,
        'paragraph': ParagraphChunker,
        'code': CodeChunker,
    }
    
    chunker_class = strategies.get(strategy, FixedSizeChunker)
    return chunker_class(**kwargs)



class ChunkerFactory:
    """
    Factory for creating chunking strategies
    
    Design Pattern: Factory + Facade
    Simplifies chunker creation with sensible defaults
    """
    
    @staticmethod
    def create_chunker(strategy: str, **kwargs) -> ChunkingStrategy:
        """
        Create chunker instance
        
        Args:
            strategy: 'fixed', 'sentence', 'paragraph', or 'code'
            **kwargs: Strategy-specific parameters
        
        Returns:
            ChunkingStrategy instance
        """
        return get_chunker(strategy, **kwargs)
