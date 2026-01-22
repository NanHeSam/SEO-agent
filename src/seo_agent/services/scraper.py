"""Blog scraping service using BeautifulSoup."""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from seo_agent.models.blog_post import BlogPost, ExistingPost, ScrapedContent


class BlogScraper:
    """Service for scraping blog content from the target site."""

    def __init__(
        self,
        base_url: str = "https://jobnova.ai/blog",
        sitemap_url: str = "https://jobnova.ai/sitemap.xml",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.sitemap_url = sitemap_url
        self.timeout = timeout

    async def fetch_urls_from_sitemap(self, max_urls: int = 100) -> list[str]:
        """Fetch blog post URLs from sitemap.xml."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(self.sitemap_url)
                if response.status_code != 200:
                    return []

                return self._parse_sitemap(response.text, max_urls)
            except httpx.HTTPError:
                return []

    def _parse_sitemap(self, xml_content: str, max_urls: int) -> list[str]:
        """Parse sitemap XML and extract blog post URLs."""
        urls = []
        try:
            # Handle namespaced XML
            # Remove namespace for easier parsing
            xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content, count=1)
            root = ElementTree.fromstring(xml_content)

            # Handle both sitemap index and regular sitemap
            # Check if this is a sitemap index (contains other sitemaps)
            sitemap_refs = root.findall('.//sitemap/loc')
            if sitemap_refs:
                # This is a sitemap index, we'll just get direct URLs for now
                pass

            # Find all URL locations
            for loc in root.findall('.//url/loc'):
                url = loc.text
                if url:
                    # Parse the URL path
                    parsed = urlparse(url)
                    path = parsed.path.rstrip('/')

                    # Filter for blog post URLs: must have /blog/ followed by a slug
                    # e.g., /blog/my-post-title (not just /blog)
                    if '/blog/' in path and path != '/blog':
                        urls.append(url)
                    elif '/article/' in path or '/post/' in path:
                        urls.append(url)

                if len(urls) >= max_urls:
                    break

        except ElementTree.ParseError:
            pass

        return urls[:max_urls]

    async def scrape_posts_from_sitemap(self, max_posts: int = 100) -> list[ExistingPost]:
        """Get post information from URLs found in sitemap.

        For SPAs that render content client-side, this extracts metadata
        from the URL slug rather than scraping page content.
        """
        urls = await self.fetch_urls_from_sitemap(max_urls=max_posts)

        if not urls:
            return []

        posts = []
        for url in urls:
            post = self._extract_post_from_url(url)
            if post:
                posts.append(post)

        return posts

    def _extract_post_from_url(self, url: str) -> ExistingPost | None:
        """Extract post metadata from URL (for SPA sites)."""
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')

        # Get the slug from the URL path
        # e.g., /blog/my-post-title -> my-post-title
        parts = path.split('/')
        if len(parts) < 2:
            return None

        slug = parts[-1]
        if not slug:
            return None

        # Convert slug to title
        # e.g., "in-demand-jobs-in-canada-2026" -> "In Demand Jobs In Canada 2026"
        title = self._slug_to_title(slug)

        # Try to extract category from URL structure
        category = ""
        if len(parts) > 2 and parts[-2] != "blog":
            category = parts[-2]

        return ExistingPost(
            title=title,
            url=url,
            category=category,
            excerpt="",
            published_date=None,
        )

    def _slug_to_title(self, slug: str) -> str:
        """Convert URL slug to readable title."""
        # Replace hyphens with spaces
        title = slug.replace('-', ' ').replace('_', ' ')
        # Remove common URL artifacts
        title = re.sub(r'\s+', ' ', title)
        # Title case
        title = title.title()
        return title

    def _extract_post_metadata(self, html: str, url: str) -> ExistingPost | None:
        """Extract post metadata from a page."""
        soup = BeautifulSoup(html, "html.parser")

        # Get title from various sources
        title = None

        # Try meta og:title first
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]

        # Try page title
        if not title:
            title_elem = soup.find("title")
            if title_elem:
                title = title_elem.get_text(strip=True)

        # Try h1
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        if not title:
            return None

        # Get excerpt from meta description
        excerpt = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            excerpt = meta_desc["content"][:300]

        # Try to extract category from URL or breadcrumbs
        category = ""
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.strip("/").split("/")
        if len(path_parts) > 1 and path_parts[0] == "blog":
            category = path_parts[1] if len(path_parts) > 2 else ""

        return ExistingPost(
            title=title,
            url=url,
            category=category,
            excerpt=excerpt,
            published_date=None,
        )

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
        """Scrape all posts from the blog using sitemap."""
        # Use sitemap as primary method
        posts = await self.scrape_posts_from_sitemap(max_posts=max_posts)
        if posts:
            return posts

        # Fallback to category pages if sitemap fails
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


def create_scraper(
    base_url: str = "https://jobnova.ai/blog",
    sitemap_url: str = "https://jobnova.ai/sitemap.xml",
) -> BlogScraper:
    """Factory function to create a blog scraper."""
    return BlogScraper(base_url=base_url, sitemap_url=sitemap_url)
