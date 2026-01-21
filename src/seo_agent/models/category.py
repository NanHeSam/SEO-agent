"""Category model for blog content organization."""

from datetime import datetime

from pydantic import BaseModel, Field


class Category(BaseModel):
    """Represents a blog content category."""

    name: str = Field(..., description="Category name/slug")
    display_name: str = Field(default="", description="Human-readable category name")
    description: str = Field(default="", description="Category description")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    post_count: int = Field(default=0, description="Number of posts in this category")

    def __init__(self, **data):
        super().__init__(**data)
        if not self.display_name:
            # Convert slug to display name
            self.display_name = self.name.replace("-", " ").title()

    class Config:
        json_schema_extra = {
            "example": {
                "name": "remote-work",
                "display_name": "Remote Work",
                "description": "Articles about remote work tips and strategies",
                "post_count": 15,
            }
        }
