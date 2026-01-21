"""Keyword models for SEO research."""

from pydantic import BaseModel, Field, computed_field, field_validator


class KeywordMetrics(BaseModel):
    """Metrics for a keyword from DataForSEO."""

    search_volume: int = Field(default=0, description="Monthly search volume")
    keyword_difficulty: float = Field(default=0.0, description="Keyword difficulty score (0-100)")
    cpc: float = Field(default=0.0, description="Cost per click in USD")
    competition: float = Field(default=0.0, description="Competition level (0-1)")
    competition_level: str = Field(default="", description="Competition level category")

    @field_validator("keyword_difficulty", "cpc", mode="before")
    @classmethod
    def convert_none_to_zero(cls, v):
        """Convert None values to 0.0."""
        return 0.0 if v is None else v

    @field_validator("competition", mode="before")
    @classmethod
    def convert_competition(cls, v):
        """Convert competition to float, handling string values."""
        if v is None:
            return 0.0
        if isinstance(v, str):
            # Map string competition levels to numeric values
            mapping = {"LOW": 0.25, "MEDIUM": 0.5, "HIGH": 0.75, "": 0.0}
            return mapping.get(v.upper(), 0.0)
        return float(v)

    @field_validator("search_volume", mode="before")
    @classmethod
    def convert_none_volume_to_zero(cls, v):
        """Convert None volume to 0."""
        return 0 if v is None else v


class Keyword(BaseModel):
    """Represents a keyword for SEO targeting."""

    keyword: str = Field(..., description="The keyword phrase")
    metrics: KeywordMetrics = Field(default_factory=KeywordMetrics)
    source: str = Field(default="suggested", description="Source of the keyword")
    is_primary: bool = Field(default=False, description="Whether this is a primary keyword")

    @computed_field
    @property
    def is_qualified(self) -> bool:
        """Check if keyword meets quality thresholds."""
        return (
            self.metrics.search_volume >= 5000
            and self.metrics.keyword_difficulty <= 30
        )

    def qualifies(self, min_volume: int = 5000, max_kd: float = 30) -> bool:
        """Check if keyword meets custom quality thresholds."""
        return (
            self.metrics.search_volume >= min_volume
            and self.metrics.keyword_difficulty <= max_kd
        )

    class Config:
        json_schema_extra = {
            "example": {
                "keyword": "remote work tips for beginners",
                "metrics": {
                    "search_volume": 8500,
                    "keyword_difficulty": 25,
                    "cpc": 2.50,
                    "competition": 0.45,
                    "competition_level": "MEDIUM",
                },
                "source": "dataforseo",
                "is_primary": True,
            }
        }


class KeywordGroup(BaseModel):
    """A group of related keywords for a topic."""

    primary_keyword: Keyword
    secondary_keywords: list[Keyword] = Field(default_factory=list)
    topic: str = Field(default="", description="Associated topic/title")

    @property
    def all_keywords(self) -> list[Keyword]:
        """Get all keywords in the group."""
        return [self.primary_keyword] + self.secondary_keywords

    @property
    def keyword_strings(self) -> list[str]:
        """Get all keyword strings."""
        return [kw.keyword for kw in self.all_keywords]
