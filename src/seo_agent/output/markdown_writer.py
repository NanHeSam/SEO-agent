"""Markdown output writer with YAML frontmatter."""

import re
from datetime import datetime
from pathlib import Path

import aiofiles
import yaml

from seo_agent.models.article import Article
from seo_agent.models.image import GeneratedImage


class MarkdownWriter:
    """Writer for Markdown files with YAML frontmatter."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def write_article(
        self,
        article: Article,
        images: list[GeneratedImage] | None = None,
        include_images_in_content: bool = True,
    ) -> Path:
        """Write article to Markdown file with frontmatter."""
        content = self._build_markdown(article, images, include_images_in_content)
        file_path = self.output_dir / f"{article.metadata.slug}.md"

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

        return file_path

    def _build_markdown(
        self,
        article: Article,
        images: list[GeneratedImage] | None = None,
        include_images_in_content: bool = True,
    ) -> str:
        """Build full Markdown content with frontmatter."""
        frontmatter = self._build_frontmatter(article, images)
        content = article.content

        # Insert image references if requested
        if include_images_in_content and images:
            content = self._insert_images(content, images)

        return f"---\n{frontmatter}---\n\n{content}"

    def _build_frontmatter(
        self,
        article: Article,
        images: list[GeneratedImage] | None = None,
    ) -> str:
        """Build YAML frontmatter."""
        data = {
            "title": article.metadata.title,
            "description": article.metadata.meta_description,
            "date": article.metadata.created_at.strftime("%Y-%m-%d"),
            "lastmod": datetime.now().strftime("%Y-%m-%d"),
            "author": article.metadata.author,
            "category": article.metadata.category,
            "tags": [article.metadata.primary_keyword] + article.metadata.secondary_keywords[:5],
            "keywords": [article.metadata.primary_keyword] + article.metadata.secondary_keywords,
            "reading_time": f"{article.metadata.reading_time_minutes} min read",
            "word_count": article.metadata.word_count,
        }

        # Add featured image if available
        if images:
            featured = next((img for img in images if img.index == 0), None)
            if featured:
                if featured.public_url:
                    data["featured_image"] = featured.public_url
                elif featured.file_path:
                    data["featured_image"] = f"../images/{featured.file_path.name}"
                data["featured_image_alt"] = featured.metadata.alt_text

        # Add SEO fields
        data["seo"] = {
            "title": article.metadata.title,
            "description": article.metadata.meta_description,
            "canonical": "",  # To be filled in
        }

        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _insert_images(
        self,
        content: str,
        images: list[GeneratedImage],
    ) -> str:
        """Insert image references at appropriate positions."""
        # Map images by section heading
        image_map = {}
        for img in images:
            if img.index == 0:  # Skip featured image
                continue
            heading = img.metadata.section_heading.lower()
            image_map[heading] = img

        # Find H2 headings and insert images after them
        lines = content.split("\n")
        result_lines = []
        current_heading = None

        for line in lines:
            result_lines.append(line)

            # Check if this is an H2 heading
            h2_match = re.match(r'^##\s+(.+)$', line)
            if h2_match:
                heading_text = h2_match.group(1).strip().lower()
                img = image_map.get(heading_text)

                if img:
                    # Add blank line and image after heading
                    result_lines.append("")
                    result_lines.append(img.markdown_reference)

        return "\n".join(result_lines)

    async def write_image_manifest(
        self,
        article: Article,
        images: list[GeneratedImage],
    ) -> Path:
        """Write image manifest file with SEO metadata."""
        manifest = {
            "article_slug": article.metadata.slug,
            "images": [],
        }

        for img in images:
            manifest["images"].append({
                "filename": img.metadata.filename,
                "alt_text": img.metadata.alt_text,
                "caption": img.metadata.caption,
                "section": img.metadata.section_heading,
                "prompt": img.prompt,
                "size": img.size,
                "index": img.index,
            })

        file_path = self.output_dir / f"{article.metadata.slug}-images.yaml"

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(yaml.dump(manifest, default_flow_style=False, allow_unicode=True))

        return file_path


def create_markdown_writer(output_dir: Path) -> MarkdownWriter:
    """Factory function to create Markdown writer."""
    return MarkdownWriter(output_dir=output_dir)
