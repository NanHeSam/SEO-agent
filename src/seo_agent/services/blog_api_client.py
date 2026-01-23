"""Blog API client for fetching posts from Libaspace Blog API."""

import json
from datetime import datetime
from pathlib import Path

import httpx

from seo_agent.models.blog_post import ApiBlogPost, BlogCache


class BlogApiClient:
    """Client for fetching blog posts from the Libaspace Blog API."""

    def __init__(self, base_url: str, cache_file: Path):
        self.base_url = base_url.rstrip("/")
        self.cache_file = cache_file

    async def fetch_all_posts(
        self,
        include_content: bool = False,
        page_size: int = 12,
    ) -> list[ApiBlogPost]:
        """Fetch all blog posts from the API, handling pagination."""
        all_posts: list[ApiBlogPost] = []
        page_number = 1

        async with httpx.AsyncClient() as client:
            while True:
                posts, metadata = await self._fetch_page(
                    client, page_number, page_size
                )

                if not posts:
                    break

                all_posts.extend(posts)

                # Check if we've fetched all posts
                total_pages = metadata.get("totalPages", 1)
                if page_number >= total_pages:
                    break

                page_number += 1

        # If not including content, clear the content field to save space
        if not include_content:
            for post in all_posts:
                post.content = ""

        return all_posts

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        page_number: int,
        page_size: int = 12,
    ) -> tuple[list[ApiBlogPost], dict]:
        """Fetch a single page of blog posts from the API."""
        url = f"{self.base_url}?pageNumber={page_number}&pageSize={page_size}"

        response = await client.get(url, timeout=30.0)
        response.raise_for_status()

        response_data = response.json()

        # API returns {code: 0, msg: "ok", data: {blogs: [...], pages: {...}}}
        data = response_data.get("data", {})
        posts_data = data.get("blogs", [])
        posts = [ApiBlogPost.model_validate(p) for p in posts_data]

        pages_info = data.get("pages", {})
        metadata = {
            "pageNumber": pages_info.get("pageNumber", page_number),
            "pageSize": pages_info.get("pageSize", page_size),
            "totalPages": pages_info.get("totalPage", 1),  # Note: API uses "totalPage" not "totalPages"
            "totalCount": pages_info.get("totalCount", len(posts)),
        }

        return posts, metadata

    async def fetch_page(
        self,
        page_number: int,
        page_size: int = 12,
    ) -> tuple[list[ApiBlogPost], dict]:
        """Public method to fetch a single page."""
        async with httpx.AsyncClient() as client:
            return await self._fetch_page(client, page_number, page_size)

    def load_cache(self) -> BlogCache | None:
        """Load cached blog posts from disk."""
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, "r") as f:
                data = json.load(f)
            return BlogCache.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            return None

    def save_cache(self, cache: BlogCache) -> Path:
        """Save blog posts cache to disk."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.cache_file, "w") as f:
            json.dump(cache.model_dump(mode="json"), f, indent=2, default=str)

        return self.cache_file

    def is_cache_valid(self, max_age_hours: int = 24) -> bool:
        """Check if cached data is still valid based on age."""
        cache = self.load_cache()
        if not cache:
            return False

        age = datetime.now() - cache.fetched_at
        return age.total_seconds() < max_age_hours * 3600

    async def get_posts(
        self,
        force: bool = False,
        include_content: bool = False,
        max_age_hours: int = 24,
    ) -> BlogCache:
        """Get posts from cache or fetch from API if needed."""
        # Check if we can use cache
        if not force:
            cache = self.load_cache()
            if cache and self.is_cache_valid(max_age_hours):
                # If we need content but cache doesn't have it, refetch
                if include_content and not cache.include_content:
                    pass  # Fall through to fetch
                else:
                    return cache

        # Fetch fresh data
        posts = await self.fetch_all_posts(include_content=include_content)

        cache = BlogCache(
            posts=posts,
            fetched_at=datetime.now(),
            total_count=len(posts),
            include_content=include_content,
        )

        self.save_cache(cache)
        return cache


def create_blog_api_client(base_url: str, cache_file: Path) -> BlogApiClient:
    """Factory function to create a BlogApiClient."""
    return BlogApiClient(base_url=base_url, cache_file=cache_file)
