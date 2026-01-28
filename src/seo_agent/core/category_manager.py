"""Category manager for storing and updating category metadata."""

from __future__ import annotations

import json
from pathlib import Path

from seo_agent.models.category import Category


class CategoryManager:
    """Manages categories persisted to a JSON file."""

    def __init__(self, categories_file: Path):
        self.categories_file = categories_file

    def _load(self) -> dict[str, dict]:
        if not self.categories_file.exists():
            return {}
        raw = self.categories_file.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        # Back-compat: list[category] -> dict[name -> category]
        if isinstance(data, list):
            out: dict[str, dict] = {}
            for item in data:
                if isinstance(item, dict) and item.get("name"):
                    out[str(item["name"])] = item
            return out
        return {}

    def _save(self, categories: dict[str, dict]) -> None:
        self.categories_file.parent.mkdir(parents=True, exist_ok=True)
        self.categories_file.write_text(
            json.dumps(categories, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def category_exists(self, name: str) -> bool:
        categories = self._load()
        return name in categories

    def add_category(self, name: str, *, display_name: str | None = None, description: str = "") -> Category:
        categories = self._load()
        if name in categories:
            raise ValueError(f"Category '{name}' already exists")
        cat = Category(name=name, display_name=display_name, description=description)
        categories[cat.name] = cat.model_dump()
        self._save(categories)
        return cat

    def list_categories(self) -> list[Category]:
        categories = self._load()
        result = [Category(**data) for data in categories.values()]
        return sorted(result, key=lambda c: c.name)

    def get_category(self, name: str) -> Category:
        categories = self._load()
        if name not in categories:
            raise ValueError(f"Category '{name}' not found")
        return Category(**categories[name])

    def remove_category(self, name: str) -> bool:
        categories = self._load()
        if name not in categories:
            return False
        categories.pop(name, None)
        self._save(categories)
        return True

    def update_category(
        self,
        name: str,
        *,
        display_name: str | None = None,
        description: str | None = None,
    ) -> Category:
        categories = self._load()
        if name not in categories:
            raise ValueError(f"Category '{name}' not found")

        current = Category(**categories[name])
        updates: dict = {}
        if display_name is not None:
            updates["display_name"] = display_name
        if description is not None:
            updates["description"] = description

        updated = current.model_copy(update=updates)
        categories[name] = updated.model_dump()
        self._save(categories)
        return updated

    def increment_post_count(self, name: str) -> Category:
        categories = self._load()
        if name not in categories:
            raise ValueError(f"Category '{name}' not found")
        current = Category(**categories[name])
        updated = current.model_copy(update={"post_count": current.post_count + 1})
        categories[name] = updated.model_dump()
        self._save(categories)
        return updated

    def get_category_names(self) -> list[str]:
        return [c.name for c in self.list_categories()]

