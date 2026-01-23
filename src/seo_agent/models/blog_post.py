"""Blog post models for existing and scraped content."""

from datetime import datetime

from pydantic import BaseModel, Field, computed_field, ConfigDict


class ApiBlogPost(BaseModel):
    """Represents a blog post from the Libaspace Blog API."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    slug: str
    title: str
    summary: str = ""
    content: str = ""  # Only populated with --include-content
    seo_title: str = Field(default="", alias="seoTitle")
    seo_description: str = Field(default="", alias="seoDescription")
    keywords: str = ""  # API returns string, not list
    cover_url: str = Field(default="", alias="coverUrl")
    publish_time: int = Field(default=0, alias="publishTime")
    author: str = ""

    @property
    def url(self) -> str:
        """Generate the full URL for this post."""
        return f"https://jobnova.ai/blog/{self.slug}"

    @property
    def keyword_list(self) -> list[str]:
        """Parse keywords string into a list."""
        if not self.keywords:
            return []
        return [k.strip() for k in self.keywords.split(",") if k.strip()]


class BlogCache(BaseModel):
    """Cache for blog posts fetched from API."""

    posts: list[ApiBlogPost]
    fetched_at: datetime
    total_count: int
    include_content: bool = False


class ExistingPost(BaseModel):
    """Represents an existing blog post scraped from the site."""

    title: str = Field(..., description="Post title")
    url: str = Field(..., description="Full URL to the post")
    category: str = Field(default="", description="Post category")
    excerpt: str = Field(default="", description="Post excerpt or summary")
    published_date: datetime | None = Field(default=None, description="Publication date")
    tags: list[str] = Field(default_factory=list, description="Post tags")

    @computed_field
    @property
    def slug(self) -> str:
        """Extract slug from URL."""
        from urllib.parse import urlparse
        path = urlparse(self.url).path
        return path.rstrip("/").split("/")[-1]

    class Config:
        json_schema_extra = {
            "example": {
                "title": "How to Write a Cover Letter",
                "url": "https://jobnova.ai/blog/how-to-write-cover-letter",
                "category": "career-advice",
                "excerpt": "Learn how to write an effective cover letter...",
                "tags": ["cover letter", "job application"],
            }
        }


class BlogPost(BaseModel):
    """Full blog post with content for cross-linking analysis."""

    title: str = Field(..., description="Post title")
    url: str = Field(..., description="Full URL to the post")
    category: str = Field(default="", description="Post category")
    content: str = Field(default="", description="Full post content")
    headings: list[str] = Field(default_factory=list, description="H2/H3 headings")
    keywords: list[str] = Field(default_factory=list, description="Extracted keywords")
    word_count: int = Field(default=0, description="Content word count")

    @computed_field
    @property
    def slug(self) -> str:
        """Extract slug from URL."""
        from urllib.parse import urlparse
        path = urlparse(self.url).path
        return path.rstrip("/").split("/")[-1]

    def extract_keywords_from_content(self) -> list[str]:
        """Extract potential keywords from content and headings."""
        import re

        # Combine title, headings for keyword extraction
        text = f"{self.title} " + " ".join(self.headings)
        text = text.lower()

        # Remove common words and extract significant phrases
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "your", "you", "their", "they", "this", "that", "these", "those",
            "how", "what", "when", "where", "why", "which", "who", "whom",
        }

        words = re.findall(r'\b[a-z]{3,}\b', text)
        keywords = [w for w in words if w not in stopwords]

        # Get unique keywords maintaining order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords[:20]

    class Config:
        json_schema_extra = {
            "example": {
                "title": "How to Write a Cover Letter",
                "url": "https://jobnova.ai/blog/how-to-write-cover-letter",
                "category": "career-advice",
                "headings": ["Why Cover Letters Matter", "Cover Letter Structure"],
                "keywords": ["cover letter", "job application", "hiring manager"],
                "word_count": 1500,
            }
        }


class ScrapedContent(BaseModel):
    """Collection of scraped blog content for a category."""

    category: str = Field(..., description="Category name")
    posts: list[ExistingPost] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.now)

    @property
    def titles(self) -> list[str]:
        """Get all post titles."""
        return [post.title for post in self.posts]

    @property
    def urls(self) -> list[str]:
        """Get all post URLs."""
        return [post.url for post in self.posts]

    def to_link_references(self) -> list[dict[str, str]]:
        """Convert to list of title/URL dicts for cross-linking."""
        return [{"title": post.title, "url": post.url} for post in self.posts]
