"""Tests for Pydantic models."""

import pytest
from datetime import datetime

from seo_agent.models.category import Category
from seo_agent.models.keyword import Keyword, KeywordMetrics, KeywordGroup
from seo_agent.models.article import Article, ArticleMetadata
from seo_agent.models.image import GeneratedImage, ImageMetadata, generate_image_filename, generate_alt_text
from seo_agent.models.blog_post import ExistingPost, BlogPost, ScrapedContent


class TestCategory:
    def test_create_category(self):
        cat = Category(name="remote-work")
        assert cat.name == "remote-work"
        assert cat.display_name == "Remote Work"

    def test_category_with_display_name(self):
        cat = Category(name="career-advice", display_name="Career Tips")
        assert cat.display_name == "Career Tips"


class TestKeyword:
    def test_create_keyword(self):
        kw = Keyword(keyword="remote work tips")
        assert kw.keyword == "remote work tips"
        assert kw.is_primary is False

    def test_keyword_with_metrics(self):
        metrics = KeywordMetrics(
            search_volume=8000,
            keyword_difficulty=25,
            cpc=2.50,
        )
        kw = Keyword(keyword="remote jobs", metrics=metrics)
        assert kw.metrics.search_volume == 8000
        assert kw.is_qualified is True

    def test_keyword_qualifies(self):
        metrics = KeywordMetrics(search_volume=3000, keyword_difficulty=40)
        kw = Keyword(keyword="test", metrics=metrics)
        assert kw.is_qualified is False
        assert kw.qualifies(min_volume=2000, max_kd=50) is True

    def test_keyword_group(self):
        primary = Keyword(keyword="main keyword", is_primary=True)
        secondary = [Keyword(keyword="secondary 1"), Keyword(keyword="secondary 2")]
        group = KeywordGroup(
            primary_keyword=primary,
            secondary_keywords=secondary,
            topic="Test Topic",
        )
        assert len(group.all_keywords) == 3
        assert group.keyword_strings == ["main keyword", "secondary 1", "secondary 2"]


class TestArticle:
    def test_article_metadata_slug(self):
        meta = ArticleMetadata(
            title="10 Remote Work Tips for Beginners",
            meta_description="Learn essential tips...",
            primary_keyword="remote work tips",
        )
        assert meta.slug == "10-remote-work-tips-for-beginners"

    def test_article_to_markdown(self):
        meta = ArticleMetadata(
            title="Test Article",
            meta_description="Test description",
            primary_keyword="test",
        )
        article = Article(metadata=meta, content="# Test\n\nContent here.")
        md = article.to_markdown()
        assert "---" in md
        assert "title: Test Article" in md
        assert "# Test" in md


class TestImage:
    def test_generate_filename(self):
        filename = generate_image_filename(
            topic_slug="remote-work-tips",
            keyword="home office",
            index=1,
        )
        assert filename == "remote-work-tips-home-office-1.png"

    def test_generate_alt_text(self):
        alt = generate_alt_text("Setting Up Your Home Office", "remote work")
        assert alt == "Setting Up Your Home Office - remote work"

    def test_generated_image_markdown(self):
        meta = ImageMetadata(
            filename="test-image.png",
            alt_text="Test image alt text",
            caption="Test caption",
        )
        img = GeneratedImage(
            metadata=meta,
            prompt="Test prompt",
            index=1,
        )
        assert "![Test image alt text]" in img.markdown_reference


class TestBlogPost:
    def test_existing_post_slug(self):
        post = ExistingPost(
            title="Test Post",
            url="https://example.com/blog/my-test-post",
        )
        assert post.slug == "my-test-post"

    def test_scraped_content_titles(self):
        posts = [
            ExistingPost(title="Post 1", url="https://example.com/1"),
            ExistingPost(title="Post 2", url="https://example.com/2"),
        ]
        scraped = ScrapedContent(category="test", posts=posts)
        assert scraped.titles == ["Post 1", "Post 2"]
        assert len(scraped.to_link_references()) == 2
