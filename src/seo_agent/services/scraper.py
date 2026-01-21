"""Blog scraping service using BeautifulSoup."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from seo_agent.models.blog_post import BlogPost, ExistingPost, ScrapedContent


class BlogScraper:
    """Service for scraping blog content from the target site."""

    def __init__(
        self,
        base_url: str = "https://jobnova.ai/blog",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def scrape_category(
        self,
        category: str,
        max_posts: int = 50,
    ) -> ScrapedContent:
        """Scrape all posts from a specific category."""
        category_url = f"{self.base_url}/category/{category}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            posts = await self._scrape_category_pages(client, category_url, max_posts)

        return ScrapedContent(
            category=category,
            posts=posts,
            scraped_at=datetime.now(),
        )

    async def scrape_all_posts(self, max_posts: int = 100) -> list[ExistingPost]:
        """Scrape all posts from the blog."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await self._scrape_category_pages(client, self.base_url, max_posts)

    async def _scrape_category_pages(
        self,
        client: httpx.AsyncClient,
        url: str,
        max_posts: int,
    ) -> list[ExistingPost]:
        """Scrape posts from paginated category pages."""
        posts = []
        page = 1

        while len(posts) < max_posts:
            page_url = f"{url}?page={page}" if page > 1 else url

            try:
                response = await client.get(page_url)
                if response.status_code != 200:
                    break

                new_posts = self._parse_post_list(response.text, url)
                if not new_posts:
                    break

                posts.extend(new_posts)
                page += 1

                # Small delay between requests
                await asyncio.sleep(0.5)

            except httpx.HTTPError:
                break

        return posts[:max_posts]

    def _parse_post_list(self, html: str, base_url: str) -> list[ExistingPost]:
        """Parse post list from HTML."""
        soup = BeautifulSoup(html, "html.parser")
        posts = []

        # Common blog post selectors - adjust based on actual site structure
        article_selectors = [
            "article",
            ".post",
            ".blog-post",
            ".entry",
            "[class*='post-item']",
            "[class*='blog-item']",
        ]

        articles = []
        for selector in article_selectors:
            articles = soup.select(selector)
            if articles:
                break

        for article in articles:
            post = self._parse_article_element(article, base_url)
            if post:
                posts.append(post)

        return posts

    def _parse_article_element(
        self,
        article,
        base_url: str,
    ) -> ExistingPost | None:
        """Parse a single article element."""
        # Find title and link
        title_elem = article.find(["h2", "h3", "h1", "a"])
        if not title_elem:
            return None

        # Get link
        link_elem = article.find("a", href=True)
        if not link_elem:
            return None

        title = title_elem.get_text(strip=True)
        href = link_elem.get("href", "")

        if not title or not href:
            return None

        # Make URL absolute
        url = urljoin(base_url, href)

        # Get excerpt if available
        excerpt_elem = article.find(["p", ".excerpt", ".summary", "[class*='excerpt']"])
        excerpt = excerpt_elem.get_text(strip=True) if excerpt_elem else ""

        # Try to get date
        date_elem = article.find(["time", ".date", "[class*='date']"])
        published_date = None
        if date_elem:
            date_str = date_elem.get("datetime") or date_elem.get_text(strip=True)
            try:
                published_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        # Try to get category
        category_elem = article.find([".category", "[class*='category']", "a[rel='category']"])
        category = category_elem.get_text(strip=True) if category_elem else ""

        return ExistingPost(
            title=title,
            url=url,
            category=category,
            excerpt=excerpt[:300] if excerpt else "",
            published_date=published_date,
        )

    async def scrape_post_content(self, url: str) -> BlogPost | None:
        """Scrape full content of a single post."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    return None

                return self._parse_post_content(response.text, url)

            except httpx.HTTPError:
                return None

    def _parse_post_content(self, html: str, url: str) -> BlogPost:
        """Parse full post content from HTML."""
        soup = BeautifulSoup(html, "html.parser")

        # Get title
        title_elem = soup.find(["h1", ".entry-title", "[class*='post-title']"])
        title = title_elem.get_text(strip=True) if title_elem else ""

        # Get main content
        content_selectors = [
            ".entry-content",
            ".post-content",
            ".article-content",
            "article",
            ".content",
            "main",
        ]

        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                break

        content = ""
        headings = []

        if content_elem:
            # Remove scripts, styles, nav elements
            for tag in content_elem.find_all(["script", "style", "nav", "aside"]):
                tag.decompose()

            content = content_elem.get_text(separator="\n", strip=True)

            # Extract headings
            for heading in content_elem.find_all(["h2", "h3"]):
                heading_text = heading.get_text(strip=True)
                if heading_text:
                    headings.append(heading_text)

        # Get category from breadcrumbs or meta
        category = ""
        breadcrumb = soup.find([".breadcrumb", "[class*='breadcrumb']"])
        if breadcrumb:
            category_link = breadcrumb.find_all("a")
            if len(category_link) > 1:
                category = category_link[-1].get_text(strip=True)

        blog_post = BlogPost(
            title=title,
            url=url,
            category=category,
            content=content,
            headings=headings,
            word_count=len(content.split()),
        )

        # Extract keywords from content
        blog_post.keywords = blog_post.extract_keywords_from_content()

        return blog_post

    async def save_scraped_content(
        self,
        content: ScrapedContent,
        output_dir: Path,
    ) -> Path:
        """Save scraped content to JSON file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"{content.category}.json"

        data = content.model_dump(mode="json")
        file_path.write_text(json.dumps(data, indent=2, default=str))

        return file_path

    def load_scraped_content(
        self,
        category: str,
        data_dir: Path,
    ) -> ScrapedContent | None:
        """Load previously scraped content from JSON file."""
        file_path = data_dir / f"{category}.json"

        if not file_path.exists():
            return None

        try:
            data = json.loads(file_path.read_text())
            return ScrapedContent(**data)
        except (json.JSONDecodeError, ValueError):
            return None


def create_scraper(base_url: str = "https://jobnova.ai/blog") -> BlogScraper:
    """Factory function to create a blog scraper."""
    return BlogScraper(base_url=base_url)
