"""Text utilities for SEO content processing."""

import re
import unicodedata
from typing import Iterator


def slugify(text: str, max_length: int = 100) -> str:
    """
    Convert text to URL-friendly slug.

    Args:
        text: Text to convert
        max_length: Maximum slug length

    Returns:
        URL-friendly slug
    """
    # Normalize unicode characters
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase
    text = text.lower()

    # Replace spaces and special chars with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)

    # Remove leading/trailing hyphens
    text = text.strip('-')

    # Truncate to max length at word boundary
    if len(text) > max_length:
        text = text[:max_length].rsplit('-', 1)[0]

    return text


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to max length, preserving words.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    truncate_at = max_length - len(suffix)

    # Find last space before truncate point
    last_space = text.rfind(' ', 0, truncate_at)
    if last_space > 0:
        return text[:last_space] + suffix

    return text[:truncate_at] + suffix


def count_words(text: str) -> int:
    """Count words in text."""
    # Remove markdown formatting
    clean = re.sub(r'[#*_`\[\]()]', '', text)
    clean = re.sub(r'!\[.*?\]\(.*?\)', '', clean)  # Remove images
    clean = re.sub(r'\[.*?\]\(.*?\)', '', clean)   # Remove links

    words = clean.split()
    return len(words)


def extract_headings(markdown: str) -> list[dict]:
    """
    Extract headings from markdown content.

    Returns list of dicts with level, text, and position.
    """
    headings = []
    lines = markdown.split('\n')

    for i, line in enumerate(lines):
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            headings.append({
                "level": len(match.group(1)),
                "text": match.group(2).strip(),
                "line": i + 1,
            })

    return headings


def calculate_keyword_density(content: str, keyword: str) -> float:
    """
    Calculate keyword density as percentage.

    Args:
        content: Full content text
        keyword: Keyword phrase to check

    Returns:
        Keyword density as percentage
    """
    content_lower = content.lower()
    keyword_lower = keyword.lower()

    word_count = count_words(content)
    if word_count == 0:
        return 0.0

    keyword_count = content_lower.count(keyword_lower)
    keyword_words = len(keyword_lower.split())

    return (keyword_count * keyword_words / word_count) * 100


def extract_first_paragraph(markdown: str) -> str:
    """Extract first non-heading paragraph from markdown."""
    lines = markdown.split('\n')

    paragraph_lines = []
    in_paragraph = False

    for line in lines:
        stripped = line.strip()

        # Skip headings and empty lines before paragraph
        if not stripped or stripped.startswith('#'):
            if in_paragraph:
                break
            continue

        in_paragraph = True
        paragraph_lines.append(stripped)

    return ' '.join(paragraph_lines)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> Iterator[str]:
    """
    Split text into overlapping chunks.

    Args:
        text: Text to chunk
        chunk_size: Target chunk size in characters
        overlap: Overlap between chunks

    Yields:
        Text chunks
    """
    if len(text) <= chunk_size:
        yield text
        return

    start = 0
    while start < len(text):
        end = start + chunk_size

        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence end within last 100 chars of chunk
            for sep in ['. ', '! ', '? ', '\n']:
                last_sep = text.rfind(sep, start + chunk_size - 100, end)
                if last_sep > start:
                    end = last_sep + 1
                    break

        yield text[start:end]
        start = end - overlap


def clean_markdown(markdown: str) -> str:
    """Remove markdown formatting, leaving plain text."""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', markdown)
    text = re.sub(r'`[^`]+`', '', text)

    # Remove images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # Convert links to just text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # Remove headers (keep text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove bold/italic
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)

    # Remove horizontal rules
    text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)

    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def format_meta_description(text: str, keyword: str = "", max_length: int = 160) -> str:
    """
    Format text as a meta description.

    Args:
        text: Source text
        keyword: Optional keyword to include
        max_length: Maximum length

    Returns:
        Formatted meta description
    """
    # Clean text
    clean = clean_markdown(text)
    clean = ' '.join(clean.split())  # Normalize whitespace

    # Get first sentence or truncate
    sentences = re.split(r'(?<=[.!?])\s+', clean)

    description = ""
    for sentence in sentences:
        if len(description) + len(sentence) + 1 <= max_length:
            description = (description + " " + sentence).strip()
        else:
            break

    if not description:
        description = truncate_text(clean, max_length)

    # Try to include keyword if not present
    if keyword and keyword.lower() not in description.lower():
        if len(description) + len(keyword) + 5 < max_length:
            # Don't force it - keep natural description
            pass

    return description
