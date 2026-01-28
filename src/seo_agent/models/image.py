"""Image models for generated images."""

from pathlib import Path

from pydantic import BaseModel, Field, computed_field


class ImageMetadata(BaseModel):
    """SEO metadata for a generated image."""

    filename: str = Field(..., description="SEO-optimized filename")
    alt_text: str = Field(..., description="Alt text for accessibility and SEO")
    short_name: str = Field(default="", description="Short display name shown under the image")
    caption: str = Field(default="", description="Image caption")
    section_heading: str = Field(default="", description="Associated section heading")
    primary_keyword: str = Field(default="", description="Primary keyword for SEO")


class GeneratedImage(BaseModel):
    """Represents a generated image with its metadata."""

    metadata: ImageMetadata
    prompt: str = Field(..., description="Prompt used for generation")
    revised_prompt: str = Field(default="", description="Model's revised prompt")
    file_path: Path | None = Field(default=None, description="Path to saved image file")
    public_url: str | None = Field(
        default=None,
        description="Public URL after uploading image to cloud storage",
    )
    size: str = Field(default="1024x1024", description="Image dimensions")
    index: int = Field(default=0, description="Image index in article")

    @computed_field
    @property
    def markdown_image(self) -> str:
        """Generate single-line Markdown image reference (no caption)."""
        if self.public_url:
            return f"![{self.metadata.alt_text}]({self.public_url})"
        filename = self.file_path.name if self.file_path else self.metadata.filename
        # Use relative path from articles/ to images/ folder
        return f"![{self.metadata.alt_text}](../images/{filename})"

    @computed_field
    @property
    def markdown_reference(self) -> str:
        """Backward-compatible alias for `markdown_image`."""
        return self.markdown_image

    @computed_field
    @property
    def markdown_block(self) -> str:
        """Generate Markdown block with image + short name under it."""
        label = (self.metadata.short_name or self.metadata.caption or self.metadata.section_heading).strip()
        if not label:
            label = "Image"
        # Blank line ensures caption renders under image (separate paragraph)
        return f"{self.markdown_image}\n\n*{label}*"

    @computed_field
    @property
    def html_reference(self) -> str:
        """Generate HTML image tag with full SEO attributes."""
        src = self.public_url
        if not src:
            filename = self.file_path.name if self.file_path else self.metadata.filename
            src = f"../images/{filename}"
        return (
            f'<img src="{src}" '
            f'alt="{self.metadata.alt_text}" '
            f'title="{self.metadata.caption or self.metadata.short_name}" '
            f'loading="lazy" />'
        )

    class Config:
        json_schema_extra = {
            "example": {
                "metadata": {
                    "filename": "remote-work-tips-home-office-1.png",
                    "alt_text": "Setting Up Your Home Office - remote work tips",
                    "caption": "Setting Up Your Home Office",
                    "section_heading": "Setting Up Your Home Office",
                    "primary_keyword": "remote work tips",
                },
                "prompt": "Professional home office setup with modern desk...",
                "size": "1024x1024",
                "index": 1,
            }
        }


def generate_image_filename(
    topic_slug: str,
    keyword: str,
    index: int,
    extension: str = "png",
) -> str:
    """
    Generate an SEO-friendly image filename.

    Format: {topic-slug}-{keyword}-{index}.{extension}
    """
    import re

    # Clean keyword for filename
    clean_keyword = keyword.lower()
    clean_keyword = re.sub(r'[^\w\s-]', '', clean_keyword)
    clean_keyword = re.sub(r'[\s_]+', '-', clean_keyword)
    clean_keyword = clean_keyword[:30]  # Limit length

    return f"{topic_slug}-{clean_keyword}-{index}.{extension}"


def generate_alt_text(section_heading: str, keyword: str) -> str:
    """
    Generate SEO-friendly alt text.

    Format: {section heading} - {keyword}
    """
    return f"{section_heading} - {keyword}"


def generate_short_name(text: str, *, max_words: int = 6, max_chars: int = 50) -> str:
    """Generate a short, human-friendly name to show under the image."""
    import re

    t = (text or "").strip()
    if not t:
        return ""

    # Prefer the first clause for brevity.
    for sep in (" — ", " – ", " - ", ":", "|"):
        if sep in t:
            candidate = t.split(sep, 1)[0].strip()
            if len(candidate) >= 3:
                t = candidate
                break

    # Remove bracketed asides.
    t = re.sub(r"\s*\([^)]*\)\s*", " ", t).strip()
    t = re.sub(r"\s+", " ", t).strip()

    words = t.split()
    if len(words) > max_words:
        t = " ".join(words[:max_words]).strip()

    if len(t) > max_chars:
        t = t[:max_chars].rsplit(" ", 1)[0].strip() or t[:max_chars].strip()

    return t
