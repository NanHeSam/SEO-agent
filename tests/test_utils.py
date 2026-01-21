"""Tests for utility functions."""

import pytest

from seo_agent.utils.text_utils import (
    slugify,
    truncate_text,
    count_words,
    extract_headings,
    calculate_keyword_density,
    clean_markdown,
    format_meta_description,
)


class TestSlugify:
    def test_basic_slugify(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert slugify("Hello, World!") == "hello-world"

    def test_multiple_spaces(self):
        assert slugify("Hello   World") == "hello-world"

    def test_max_length(self):
        result = slugify("This is a very long title that should be truncated", max_length=20)
        assert len(result) <= 20

    def test_unicode(self):
        assert slugify("Café Résumé") == "cafe-resume"


class TestTruncateText:
    def test_no_truncation_needed(self):
        assert truncate_text("Short", 100) == "Short"

    def test_truncate_at_word(self):
        result = truncate_text("Hello wonderful world", 15)
        assert result == "Hello..."

    def test_custom_suffix(self):
        result = truncate_text("Hello wonderful world", 15, suffix="…")
        assert result.endswith("…")


class TestCountWords:
    def test_basic_count(self):
        assert count_words("Hello world test") == 3

    def test_markdown_removal(self):
        assert count_words("# Hello **world** test") == 3

    def test_empty_string(self):
        assert count_words("") == 0


class TestExtractHeadings:
    def test_extract_h1_h2(self):
        md = """# Main Title

## Section 1

Content here.

## Section 2

More content.

### Subsection
"""
        headings = extract_headings(md)
        assert len(headings) == 4
        assert headings[0]["level"] == 1
        assert headings[0]["text"] == "Main Title"
        assert headings[1]["level"] == 2
        assert headings[3]["level"] == 3


class TestKeywordDensity:
    def test_calculate_density(self):
        content = "Remote work is great. Remote work tips help. Remote work tools."
        density = calculate_keyword_density(content, "remote work")
        # 3 occurrences of "remote work" (2 words each) = 6 keyword words
        # Total: 11 words, so density = (6/11) * 100 ≈ 54.5%
        assert 50 < density < 60

    def test_zero_density(self):
        content = "This is some content without the keyword."
        density = calculate_keyword_density(content, "missing")
        assert density == 0


class TestCleanMarkdown:
    def test_remove_formatting(self):
        md = "**Bold** and *italic* text"
        assert clean_markdown(md) == "Bold and italic text"

    def test_remove_links(self):
        md = "Check [this link](https://example.com) out"
        result = clean_markdown(md)
        assert "this link" in result
        assert "https" not in result

    def test_remove_images(self):
        md = "See this ![alt text](image.png) here"
        result = clean_markdown(md)
        assert "alt text" not in result
        assert "image.png" not in result


class TestFormatMetaDescription:
    def test_basic_format(self):
        text = "This is the first sentence. This is the second sentence."
        result = format_meta_description(text)
        assert len(result) <= 160

    def test_truncate_long_text(self):
        text = "A" * 200
        result = format_meta_description(text)
        assert len(result) <= 160
