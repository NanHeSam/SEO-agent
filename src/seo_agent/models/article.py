"""Article models for content generation."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, computed_field


class ArticleMetadata(BaseModel):
    """Metadata for a generated article."""

    title: str = Field(..., description="Article title (H1)")
    meta_description: str = Field(..., description="SEO meta description (150-160 chars)")
    primary_keyword: str = Field(..., description="Primary target keyword")
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str = Field(default="informational", description="Search intent type")
    author: str = Field(default="JobNova Team", description="Article author")
    created_at: datetime = Field(default_factory=datetime.now)
    word_count: int = Field(default=0, description="Article word count")
    reading_time_minutes: int = Field(default=0, description="Estimated reading time")

    @computed_field
    @property
    def slug(self) -> str:
        """Generate URL slug from title."""
        import re
        slug = self.title.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')


class Article(BaseModel):
    """Represents a complete generated article."""

    metadata: ArticleMetadata
    content: str = Field(..., description="Full article content in Markdown")
    images: list[str] = Field(default_factory=list, description="Paths to generated images")
    cover_url: str | None = Field(default=None, description="Cover image URL for blog admin API")
    cover_alt: str | None = Field(default=None, description="Cover image alt text for blog admin API")
    internal_links: list[dict[str, str]] = Field(
        default_factory=list,
        description="Internal links added to the article"
    )

    @computed_field
    @property
    def has_images(self) -> bool:
        """Check if article has images."""
        return len(self.images) > 0

    @computed_field
    @property
    def image_count(self) -> int:
        """Get number of images."""
        return len(self.images)

    def get_frontmatter(self) -> str:
        """Generate YAML frontmatter for the article."""
        import yaml

        frontmatter_data = {
            "title": self.metadata.title,
            "description": self.metadata.meta_description,
            "date": self.metadata.created_at.strftime("%Y-%m-%d"),
            "author": self.metadata.author,
            "keywords": [self.metadata.primary_keyword] + self.metadata.secondary_keywords,
            "reading_time": f"{self.metadata.reading_time_minutes} min read",
        }

        return yaml.dump(frontmatter_data, default_flow_style=False, allow_unicode=True)

    def to_markdown(self) -> str:
        """Convert article to full Markdown with frontmatter."""
        frontmatter = self.get_frontmatter()
        return f"---\n{frontmatter}---\n\n{self.content}"

    def save(self, output_dir: Path) -> Path:
        """Save article to a Markdown file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"{self.metadata.slug}.md"
        file_path.write_text(self.to_markdown())
        return file_path

    class Config:
        json_schema_extra = {
            "example": {
                "metadata": {
                    "title": "10 Remote Work Tips for Beginners",
                    "meta_description": "Discover essential remote work tips for beginners...",
                    "primary_keyword": "remote work tips",
                    "secondary_keywords": ["work from home", "remote job tips"],
                    "search_intent": "informational",
                    "word_count": 2000,
                    "reading_time_minutes": 8,
                },
                "content": "# 10 Remote Work Tips...",
                "images": ["images/remote-work-tips-1.png"],
            }
        }
