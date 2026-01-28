"""JSON output writer for structured article data."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from seo_agent.models.article import Article
from seo_agent.models.image import GeneratedImage
from seo_agent.models.keyword import KeywordGroup


class JSONWriter:
    """Writer for structured JSON output."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def write_article(
        self,
        article: Article,
        images: list[GeneratedImage] | None = None,
        keywords: KeywordGroup | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> Path:
        """Write article data to JSON file."""
        data = self._build_article_json(article, images, keywords, extra_data)
        file_path = self.output_dir / f"{article.metadata.slug}.json"

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=2, default=str, ensure_ascii=False))

        return file_path

    def _build_article_json(
        self,
        article: Article,
        images: list[GeneratedImage] | None = None,
        keywords: KeywordGroup | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build complete JSON structure for article."""
        data = {
            "version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "metadata": {
                "title": article.metadata.title,
                "slug": article.metadata.slug,
                "meta_description": article.metadata.meta_description,
                "author": article.metadata.author,
                "cover_url": getattr(article, "cover_url", None),
                "cover_alt": getattr(article, "cover_alt", None),
                "created_at": article.metadata.created_at.isoformat(),
                "word_count": article.metadata.word_count,
                "reading_time_minutes": article.metadata.reading_time_minutes,
            },
            "seo": {
                "primary_keyword": article.metadata.primary_keyword,
                "secondary_keywords": article.metadata.secondary_keywords,
                "search_intent": article.metadata.search_intent,
            },
            "content": {
                "markdown": article.content,
                "has_frontmatter": True,
            },
            "internal_links": article.internal_links,
        }

        # Add images if provided
        if images:
            data["images"] = [
                {
                    "filename": img.metadata.filename,
                    "alt_text": img.metadata.alt_text,
                    "short_name": img.metadata.short_name,
                    "caption": img.metadata.caption,
                    "section_heading": img.metadata.section_heading,
                    "size": img.size,
                    "index": img.index,
                    "file_path": str(img.file_path) if img.file_path else None,
                    "public_url": img.public_url,
                }
                for img in images
            ]

        # Add keyword research data if provided
        if keywords:
            data["keyword_research"] = {
                "primary": {
                    "keyword": keywords.primary_keyword.keyword,
                    "search_volume": keywords.primary_keyword.metrics.search_volume,
                    "keyword_difficulty": keywords.primary_keyword.metrics.keyword_difficulty,
                    "cpc": keywords.primary_keyword.metrics.cpc,
                },
                "secondary": [
                    {
                        "keyword": kw.keyword,
                        "search_volume": kw.metrics.search_volume,
                        "keyword_difficulty": kw.metrics.keyword_difficulty,
                    }
                    for kw in keywords.secondary_keywords
                ],
            }

        # Add any extra data
        if extra_data:
            data["extra"] = extra_data

        return data

    async def write_batch_summary(
        self,
        articles: list[Article],
        filename: str = "batch_summary.json",
    ) -> Path:
        """Write summary of multiple generated articles."""
        summary = {
            "generated_at": datetime.now().isoformat(),
            "total_articles": len(articles),
            "total_word_count": sum(a.metadata.word_count for a in articles),
            "articles": [
                {
                    "title": a.metadata.title,
                    "slug": a.metadata.slug,
                    "category": a.metadata.category,
                    "primary_keyword": a.metadata.primary_keyword,
                    "word_count": a.metadata.word_count,
                }
                for a in articles
            ],
        }

        file_path = self.output_dir / filename

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(summary, indent=2, default=str))

        return file_path

    async def write_keyword_report(
        self,
        category: str,
        keywords: list[dict],
        filename: str | None = None,
    ) -> Path:
        """Write keyword research report."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "category": category,
            "total_keywords": len(keywords),
            "qualified_keywords": len([k for k in keywords if k.get("qualified", False)]),
            "keywords": keywords,
        }

        file_path = self.output_dir / (filename or f"{category}-keywords.json")

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(report, indent=2, default=str))

        return file_path


def create_json_writer(output_dir: Path) -> JSONWriter:
    """Factory function to create JSON writer."""
    return JSONWriter(output_dir=output_dir)
