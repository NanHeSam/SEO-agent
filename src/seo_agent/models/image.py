"""Image models for generated images."""

from pathlib import Path

from pydantic import BaseModel, Field, computed_field


class ImageMetadata(BaseModel):
    """SEO metadata for a generated image."""

    filename: str = Field(..., description="SEO-optimized filename")
    alt_text: str = Field(..., description="Alt text for accessibility and SEO")
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
    def markdown_reference(self) -> str:
        """Generate Markdown image reference with relative path to images folder."""
        if self.public_url:
            return f"![{self.metadata.alt_text}]({self.public_url})"
        filename = self.file_path.name if self.file_path else self.metadata.filename
        # Use relative path from articles/ to images/ folder
        return f"![{self.metadata.alt_text}](../images/{filename})"

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
            f'title="{self.metadata.caption}" '
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
