import json

from seo_agent.models.article import Article, ArticleMetadata
from seo_agent.services.blog_publisher import build_blog_payload, load_article_from_json
from seo_agent.utils.text_utils import markdown_to_html


def test_markdown_to_html_basic():
    html = markdown_to_html("# Title\n\nHello world.")
    assert "<h1>Title</h1>" in html
    assert "<p>Hello world.</p>" in html


def test_build_blog_payload_defaults():
    metadata = ArticleMetadata(
        title="Test Title",
        meta_description="Short description",
        primary_keyword="primary",
        secondary_keywords=["secondary"],
        search_intent="informational",
        category="",
        author="Author",
        word_count=10,
        reading_time_minutes=1,
    )
    article = Article(metadata=metadata, content="# Test Title\n\nBody text.")

    payload = build_blog_payload(article)

    assert payload["slug"] == "test-title"
    assert payload["title"] == "Test Title"
    assert payload["author"] == "Author"
    assert payload["status"] == 1
    assert payload["noIndex"] == 0
    assert "<h1>Test Title</h1>" in payload["content"]


def test_load_article_from_json(tmp_path):
    data = {
        "metadata": {
            "title": "Loaded Title",
            "slug": "loaded-title",
            "meta_description": "Loaded description",
            "author": "Loaded Author",
            "category": "",
            "created_at": "2026-01-23T12:00:00",
            "word_count": 100,
            "reading_time_minutes": 1,
        },
        "seo": {
            "primary_keyword": "primary",
            "secondary_keywords": ["secondary"],
            "search_intent": "informational",
        },
        "content": {
            "markdown": "# Loaded Title\n\nBody",
            "has_frontmatter": True,
        },
        "internal_links": [],
    }

    path = tmp_path / "article.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    article = load_article_from_json(path)

    assert article.metadata.title == "Loaded Title"
    assert article.content.startswith("# Loaded Title")
