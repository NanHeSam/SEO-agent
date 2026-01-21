"""Category management for blog content."""

import json
from datetime import datetime
from pathlib import Path

from seo_agent.models.category import Category


class CategoryManager:
    """Manager for blog categories with CRUD operations."""

    def __init__(self, categories_file: Path):
        self.categories_file = categories_file
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensure the categories file exists."""
        if not self.categories_file.exists():
            self.categories_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_categories([])

    def _load_categories(self) -> list[Category]:
        """Load categories from file."""
        try:
            data = json.loads(self.categories_file.read_text())
            return [Category(**cat) for cat in data]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_categories(self, categories: list[Category]) -> None:
        """Save categories to file."""
        data = [cat.model_dump(mode="json") for cat in categories]
        self.categories_file.write_text(json.dumps(data, indent=2, default=str))

    def list_categories(self) -> list[Category]:
        """List all categories."""
        return self._load_categories()

    def get_category(self, name: str) -> Category | None:
        """Get a category by name."""
        categories = self._load_categories()
        for cat in categories:
            if cat.name.lower() == name.lower():
                return cat
        return None

    def add_category(
        self,
        name: str,
        display_name: str = "",
        description: str = "",
    ) -> Category:
        """Add a new category."""
        categories = self._load_categories()

        # Check if category already exists
        for cat in categories:
            if cat.name.lower() == name.lower():
                raise ValueError(f"Category '{name}' already exists")

        # Create new category
        category = Category(
            name=name.lower().replace(" ", "-"),
            display_name=display_name or name.replace("-", " ").title(),
            description=description,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        categories.append(category)
        self._save_categories(categories)

        return category

    def remove_category(self, name: str) -> bool:
        """Remove a category by name."""
        categories = self._load_categories()
        original_count = len(categories)

        categories = [cat for cat in categories if cat.name.lower() != name.lower()]

        if len(categories) < original_count:
            self._save_categories(categories)
            return True

        return False

    def update_category(
        self,
        name: str,
        display_name: str | None = None,
        description: str | None = None,
        post_count: int | None = None,
    ) -> Category | None:
        """Update a category."""
        categories = self._load_categories()

        for i, cat in enumerate(categories):
            if cat.name.lower() == name.lower():
                if display_name is not None:
                    cat.display_name = display_name
                if description is not None:
                    cat.description = description
                if post_count is not None:
                    cat.post_count = post_count

                cat.updated_at = datetime.now()
                categories[i] = cat

                self._save_categories(categories)
                return cat

        return None

    def increment_post_count(self, name: str) -> Category | None:
        """Increment the post count for a category."""
        category = self.get_category(name)
        if category:
            return self.update_category(name, post_count=category.post_count + 1)
        return None

    def category_exists(self, name: str) -> bool:
        """Check if a category exists."""
        return self.get_category(name) is not None

    def get_category_names(self) -> list[str]:
        """Get list of all category names."""
        return [cat.name for cat in self._load_categories()]


def create_category_manager(categories_file: Path) -> CategoryManager:
    """Factory function to create category manager."""
    return CategoryManager(categories_file=categories_file)
