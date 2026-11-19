"""
Text Processing Utilities

Design Decision: High-quality text cleaning for better RAG performance
- Remove noise while preserving semantic meaning
- Normalize whitespace without losing structure
- Handle special characters intelligently
- Preserve important formatting (lists, code blocks)
"""
import re
import unicodedata
from typing import List, Optional


def clean_text(text: str, preserve_structure: bool = True) -> str:
    """
    Clean and normalize text for processing
    
    Algorithm:
    1. Normalize Unicode (NFKC form)
    2. Remove control characters
    3. Normalize whitespace
    4. Remove excessive newlines
    5. Strip leading/trailing whitespace
    
    Args:
        text: Input text
        preserve_structure: Keep paragraph breaks and list formatting
    
    Time Complexity: O(n) where n = text length
    """
    if not text:
        return ""
    
    # Step 1: Normalize Unicode (handles accented characters, etc.)
    text = unicodedata.normalize('NFKC', text)
    
    # Step 2: Remove control characters (except newlines and tabs)
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\n\t')
    
    # Step 3: Normalize whitespace
    if preserve_structure:
        # Keep paragraph breaks (double newlines)
        text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 newlines
        text = re.sub(r'[ \t]+', ' ', text)  # Normalize spaces/tabs
        text = re.sub(r'^\s+', '', text, flags=re.MULTILINE)  # Remove leading whitespace per line
    else:
        # Collapse all whitespace
        text = re.sub(r'\s+', ' ', text)
    
    # Step 4: Strip
    text = text.strip()
    
    return text


def remove_urls(text: str, replacement: str = '[URL]') -> str:
    """
    Remove or replace URLs
    
    Pattern: Matches http://, https://, www., ftp://
    
    Time Complexity: O(n)
    """
    url_pattern = r'https?://\S+|www\.\S+|ftp://\S+'
    return re.sub(url_pattern, replacement, text)


def remove_emails(text: str, replacement: str = '[EMAIL]') -> str:
    """
    Remove or replace email addresses
    
    Pattern: Standard email regex
    
    Time Complexity: O(n)
    """
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.sub(email_pattern, replacement, text)


def remove_phone_numbers(text: str, replacement: str = '[PHONE]') -> str:
    """
    Remove or replace phone numbers
    
    Patterns: Common formats (US, international)
    
    Time Complexity: O(n)
    """
    phone_patterns = [
        r'\+?1?\d{9,15}',  # International format
        r'\(\d{3}\)\s*\d{3}-\d{4}',  # (123) 456-7890
        r'\d{3}-\d{3}-\d{4}',  # 123-456-7890
        r'\d{3}\.\d{3}\.\d{4}',  # 123.456.7890
    ]
    for pattern in phone_patterns:
        text = re.sub(pattern, replacement, text)
    return text


def extract_code_blocks(text: str) -> List[dict]:
    """
    Extract code blocks from markdown
    
    Pattern: ```language\ncode\n```
    
    Returns: List of {language, code, start_pos, end_pos}
    
    Time Complexity: O(n)
    """
    pattern = r'```(\w+)?\n(.*?)\n```'
    matches = re.finditer(pattern, text, re.DOTALL)
    
    code_blocks = []
    for match in matches:
        code_blocks.append({
            'language': match.group(1) or 'text',
            'code': match.group(2),
            'start_pos': match.start(),
            'end_pos': match.end(),
        })
    
    return code_blocks


def remove_code_blocks(text: str, replacement: str = '[CODE_BLOCK]') -> str:
    """
    Remove markdown code blocks
    
    Useful when you want to process text without code
    
    Time Complexity: O(n)
    """
    pattern = r'```.*?```'
    return re.sub(pattern, replacement, text, flags=re.DOTALL)


def extract_bullet_points(text: str) -> List[str]:
    """
    Extract bullet points and list items
    
    Patterns:
    - Lines starting with -, *, •
    - Numbered lists (1., 2., etc.)
    
    Time Complexity: O(n)
    """
    bullet_pattern = r'^\s*[-*•]\s+(.+)$'
    numbered_pattern = r'^\s*\d+\.\s+(.+)$'
    
    lines = text.split('\n')
    bullet_points = []
    
    for line in lines:
        # Check bullet points
        match = re.match(bullet_pattern, line)
        if match:
            bullet_points.append(match.group(1).strip())
            continue
        
        # Check numbered lists
        match = re.match(numbered_pattern, line)
        if match:
            bullet_points.append(match.group(1).strip())
    
    return bullet_points


def truncate_text(
    text: str,
    max_length: int,
    suffix: str = '...',
    preserve_words: bool = True
) -> str:
    """
    Truncate text to maximum length
    
    Args:
        text: Input text
        max_length: Maximum character count
        suffix: Append to truncated text
        preserve_words: Don't break mid-word
    
    Time Complexity: O(n)
    """
    if len(text) <= max_length:
        return text
    
    truncate_at = max_length - len(suffix)
    
    if preserve_words:
        # Find last space before truncate point
        last_space = text.rfind(' ', 0, truncate_at)
        if last_space > 0:
            truncate_at = last_space
    
    return text[:truncate_at].strip() + suffix


def count_words(text: str) -> int:
    """
    Count words in text
    
    More accurate than len(text.split())
    Handles punctuation, multiple spaces, etc.
    
    Time Complexity: O(n)
    """
    # Remove punctuation and split
    words = re.findall(r'\b\w+\b', text)
    return len(words)


def count_tokens_approx(text: str) -> int:
    """
    Approximate token count for LLMs
    
    Rule of thumb: 1 token ≈ 4 characters (for English)
    More accurate: 1 token ≈ 0.75 words
    
    This is approximate! For exact count, use tiktoken library
    
    Time Complexity: O(n)
    """
    # Method 1: Character-based (simpler)
    char_based = len(text) // 4
    
    # Method 2: Word-based (more accurate)
    word_count = count_words(text)
    word_based = int(word_count * 1.3)  # 1 word ≈ 1.3 tokens
    
    # Return average
    return (char_based + word_based) // 2


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences
    
    Algorithm: Handle common sentence boundaries
    - Period followed by space and capital letter
    - Question marks and exclamation points
    - Handle abbreviations (Dr., Mr., etc.)
    
    Time Complexity: O(n)
    """
    # Common abbreviations that shouldn't split
    abbreviations = r'(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|Inc|Ltd|Co|vs|etc|ie|eg)'
    
    # Replace abbreviations temporarily
    text = re.sub(f'({abbreviations})\\.', r'\1<PERIOD>', text)
    
    # Split on sentence boundaries
    sentences = re.split(r'[.!?]+\s+(?=[A-Z])', text)
    
    # Restore abbreviations
    sentences = [s.replace('<PERIOD>', '.').strip() for s in sentences]
    
    # Filter empty
    return [s for s in sentences if s]


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """
    Extract keywords using simple frequency-based method
    
    Algorithm:
    1. Tokenize and lowercase
    2. Remove stop words
    3. Count frequencies
    4. Return top N
    
    Note: For production, use TF-IDF or RAKE algorithm
    
    Time Complexity: O(n log n)
    """
    # Common English stop words (abbreviated list)
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
        'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
    }
    
    # Tokenize
    words = re.findall(r'\b\w+\b', text.lower())
    
    # Filter stop words and short words
    words = [w for w in words if w not in stop_words and len(w) > 3]
    
    # Count frequencies
    from collections import Counter
    word_freq = Counter(words)
    
    # Return top N
    return [word for word, _ in word_freq.most_common(top_n)]


def normalize_quotes(text: str) -> str:
    """
    Normalize different quote types to standard quotes
    
    ' → '
    " → "
    `` → "
    
    Time Complexity: O(n)
    """
    # Map of smart quotes to standard quotes
    quote_map = {
        ''': "'",
        ''': "'",
        '"': '"',
        '"': '"',
        '``': '"',
        "''": '"',
    }
    
    for smart, standard in quote_map.items():
        text = text.replace(smart, standard)
    
    return text


def remove_html_tags(text: str) -> str:
    """
    Remove HTML tags from text
    
    Simple regex-based removal
    For complex HTML, use BeautifulSoup
    
    Time Complexity: O(n)
    """
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode HTML entities
    import html
    text = html.unescape(text)
    
    return text


def deduplicate_lines(text: str, preserve_order: bool = True) -> str:
    """
    Remove duplicate lines while optionally preserving order
    
    Useful for cleaning up repeated content
    
    Time Complexity: O(n) with preserve_order, O(n log n) without
    """
    lines = text.split('\n')
    
    if preserve_order:
        seen = set()
        unique_lines = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
        return '\n'.join(unique_lines)
    else:
        return '\n'.join(list(set(lines)))
