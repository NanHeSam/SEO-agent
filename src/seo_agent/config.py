"""Configuration management using pydantic-settings."""

from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI settings (optional for commands that don't need APIs)
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-5.2", description="OpenAI model for text generation")
    openai_image_model: str = Field(
        default="dall-e-3", description="OpenAI model for image generation"
    )

    # DataForSEO settings (optional for commands that don't need APIs)
    # Base64-encoded "login:password" - generate with: echo -n "login:password" | base64
    dataforseo_api_credentials: str = Field(
        default="", description="DataForSEO API credentials (base64-encoded 'login:password')"
    )

    # Target blog settings
    target_blog_url: str = Field(
        default="https://jobnova.ai/blog", description="Target blog URL to analyze"
    )
    target_sitemap_url: str = Field(
        default="https://jobnova.ai/sitemap.xml", description="Sitemap URL for blog discovery"
    )
    blog_api_url: str = Field(
        default="https://api.libaspace.com/api/blogs", description="Blog API URL for fetching posts"
    )
    blog_api_admin_url: str = Field(
        default="https://test-api-admin.libaspace.com/api",
        description="Blog admin API base URL for creating posts",
    )
    blog_api_token: str = Field(default="", description="Blog admin API JWT token")
    blog_cache_max_age_hours: int = Field(
        default=24, description="Maximum age of blog cache in hours"
    )

    # Keyword research defaults
    default_min_volume: int = Field(
        default=1000, description="Minimum search volume for keywords"
    )
    default_max_kd: int = Field(
        default=30, description="Maximum keyword difficulty score"
    )

    # Paths
    data_dir: Path = Field(default=Path("./data"), description="Data directory path")

    @property
    def blog_cache_file(self) -> Path:
        """Path to blog cache JSON file."""
        return self.data_dir / "blog_cache.json"

    @property
    def existing_content_dir(self) -> Path:
        """Path to existing content directory."""
        return self.data_dir / "existing_content"

    @property
    def generated_articles_dir(self) -> Path:
        """Path to generated articles directory."""
        return self.data_dir / "generated" / "articles"

    @property
    def generated_images_dir(self) -> Path:
        """Path to generated images directory."""
        return self.data_dir / "generated" / "images"

    @property
    def logs_dir(self) -> Path:
        """Path to workflow logs directory."""
        return self.data_dir / "logs"

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.existing_content_dir.mkdir(parents=True, exist_ok=True)
        self.generated_articles_dir.mkdir(parents=True, exist_ok=True)
        self.generated_images_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def has_openai_key(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.openai_api_key)

    @property
    def has_dataforseo_credentials(self) -> bool:
        """Check if DataForSEO credentials are configured."""
        return bool(self.dataforseo_api_credentials)

    def validate_api_keys(self) -> None:
        """Validate that required API keys are configured. Raises ValueError if not."""
        missing = []
        if not self.has_openai_key:
            missing.append("OPENAI_API_KEY")
        if not self.has_dataforseo_credentials:
            missing.append("DATAFORSEO_API_CREDENTIALS")

        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}. "
                "Please set these in your .env file or environment variables."
            )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
