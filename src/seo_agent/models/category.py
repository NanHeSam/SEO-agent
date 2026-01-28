"""Category model for organizing blog content."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class Category(BaseModel):
    """Represents a blog category."""

    name: str = Field(..., description="Category slug (e.g., remote-work)")
    display_name: str | None = Field(
        default=None, description="Human-friendly category name"
    )
    description: str = Field(default="", description="Optional category description")
    post_count: int = Field(default=0, description="Number of posts in this category")

    @model_validator(mode="after")
    def _default_display_name(self) -> "Category":
        if not self.display_name:
            normalized = self.name.replace("_", "-").replace("-", " ").strip()
            self.display_name = " ".join(w.capitalize() for w in normalized.split())
        return self

