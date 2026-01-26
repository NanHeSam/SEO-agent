"""Blog publishing utilities for the admin API."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from seo_agent.models.article import Article, ArticleMetadata
from seo_agent.services.blog_api_client import BlogAdminClient
from seo_agent.utils.text_utils import (
    clean_markdown,
    extract_first_paragraph,
    format_meta_description,
    markdown_to_html,
    truncate_text,
)


def load_article_from_json(file_path: Path) -> Article:
    """Load an Article from the JSON output writer format."""
    data = json.loads(file_path.read_text(encoding="utf-8"))
    metadata = data.get("metadata", {})
    seo = data.get("seo", {})
    content = data.get("content", {})

    created_at = metadata.get("created_at")
    created_dt = datetime.fromisoformat(created_at) if created_at else datetime.now()

    article_metadata = ArticleMetadata(
        title=metadata.get("title", ""),
        meta_description=metadata.get("meta_description", ""),
        primary_keyword=seo.get("primary_keyword", ""),
        secondary_keywords=seo.get("secondary_keywords", []),
        search_intent=seo.get("search_intent", "informational"),
        author=metadata.get("author", "JobNova Team"),
        created_at=created_dt,
        word_count=metadata.get("word_count", 0),
        reading_time_minutes=metadata.get("reading_time_minutes", 0),
    )

    images_data = data.get("images", [])
    images = [img.get("file_path") for img in images_data if img.get("file_path")]

    return Article(
        metadata=article_metadata,
        content=content.get("markdown", ""),
        images=images,
        cover_url=metadata.get("cover_url") or None,
        cover_alt=metadata.get("cover_alt") or None,
        internal_links=data.get("internal_links", []),
    )


def build_blog_payload(
    article: Article,
    *,
    status: int = 1,
    summary: str | None = None,
    publish_time: int | None = None,
    seo_title: str | None = None,
    seo_description: str | None = None,
    keywords: list[str] | None = None,
    cover_url: str | None = None,
    cover_alt: str | None = None,
    no_index: int = 0,
) -> Mapping[str, Any]:
    """Build blog API payload from an Article."""
    markdown_content = article.content
    html_content = markdown_to_html(markdown_content)

    fallback_summary = extract_first_paragraph(markdown_content)
    raw_summary = summary or article.metadata.meta_description or fallback_summary
    clean_summary = truncate_text(clean_markdown(raw_summary), 500)

    resolved_seo_title = seo_title or article.metadata.title
    resolved_seo_description = (
        seo_description
        or article.metadata.meta_description
        or format_meta_description(markdown_content, article.metadata.primary_keyword)
    )

    keyword_list = keywords if keywords is not None else [
        article.metadata.primary_keyword,
        *article.metadata.secondary_keywords,
    ]
    keyword_list = [kw.strip() for kw in keyword_list if kw and kw.strip()]
    keywords_str = ",".join(keyword_list)

    payload = {
        "slug": article.metadata.slug,
        "title": article.metadata.title,
        "author": article.metadata.author,
        "status": status,
        "summary": clean_summary,
        "content": html_content,
        "noIndex": no_index,
    }

    if publish_time is not None:
        payload["publishTime"] = publish_time
    if resolved_seo_title:
        payload["seoTitle"] = resolved_seo_title
    if resolved_seo_description:
        payload["seoDescription"] = resolved_seo_description
    if keywords_str:
        payload["keywords"] = keywords_str
    if cover_url:
        payload["coverUrl"] = cover_url
    if cover_alt:
        payload["coverAlt"] = cover_alt

    return payload


class BlogPublisher:
    """Publish articles to the blog admin API."""

    def __init__(self, admin_client: BlogAdminClient):
        self.admin_client = admin_client

    async def publish_article(
        self,
        article: Article,
        *,
        status: int = 1,
        summary: str | None = None,
        publish_time: int | None = None,
        seo_title: str | None = None,
        seo_description: str | None = None,
        keywords: list[str] | None = None,
        cover_url: str | None = None,
        cover_alt: str | None = None,
        no_index: int = 0,
    ) -> Mapping[str, Any]:
        payload = build_blog_payload(
            article,
            status=status,
            summary=summary,
            publish_time=publish_time,
            seo_title=seo_title,
            seo_description=seo_description,
            keywords=keywords,
            cover_url=cover_url,
            cover_alt=cover_alt,
            no_index=no_index,
        )
        return await self.admin_client.create_blog(payload)
