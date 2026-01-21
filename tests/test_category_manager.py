"""Tests for category manager."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from seo_agent.core.category_manager import CategoryManager


@pytest.fixture
def temp_categories_file():
    """Create a temporary categories file."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "categories.json"


class TestCategoryManager:
    def test_add_category(self, temp_categories_file):
        manager = CategoryManager(temp_categories_file)
        cat = manager.add_category("remote-work", description="Remote work tips")

        assert cat.name == "remote-work"
        assert cat.display_name == "Remote Work"
        assert manager.category_exists("remote-work")

    def test_add_duplicate_category(self, temp_categories_file):
        manager = CategoryManager(temp_categories_file)
        manager.add_category("test")

        with pytest.raises(ValueError, match="already exists"):
            manager.add_category("test")

    def test_list_categories(self, temp_categories_file):
        manager = CategoryManager(temp_categories_file)
        manager.add_category("cat1")
        manager.add_category("cat2")

        categories = manager.list_categories()
        assert len(categories) == 2
        assert {c.name for c in categories} == {"cat1", "cat2"}

    def test_remove_category(self, temp_categories_file):
        manager = CategoryManager(temp_categories_file)
        manager.add_category("to-remove")

        assert manager.remove_category("to-remove") is True
        assert manager.category_exists("to-remove") is False

    def test_remove_nonexistent(self, temp_categories_file):
        manager = CategoryManager(temp_categories_file)
        assert manager.remove_category("nonexistent") is False

    def test_update_category(self, temp_categories_file):
        manager = CategoryManager(temp_categories_file)
        manager.add_category("test", description="Original")

        updated = manager.update_category("test", description="Updated")
        assert updated.description == "Updated"

    def test_increment_post_count(self, temp_categories_file):
        manager = CategoryManager(temp_categories_file)
        manager.add_category("test")

        manager.increment_post_count("test")
        cat = manager.get_category("test")
        assert cat.post_count == 1

    def test_get_category_names(self, temp_categories_file):
        manager = CategoryManager(temp_categories_file)
        manager.add_category("alpha")
        manager.add_category("beta")

        names = manager.get_category_names()
        assert "alpha" in names
        assert "beta" in names
