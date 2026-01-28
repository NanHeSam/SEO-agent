"""Utilities for DataForSEO location cache."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocationOption:
    """Simplified location option for CLI selection."""

    code: int
    name: str
    country_iso_code: str | None = None
    location_type: str | None = None


def load_location_cache(cache_path: Path) -> list[dict[str, Any]]:
    """Load cached locations JSON from disk."""
    if not cache_path.exists():
        return []
    try:
        raw = cache_path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        data = __import__("json").loads(raw)
    except ValueError:
        return []
    if isinstance(data, dict):
        locations = data.get("locations", [])
        return locations if isinstance(locations, list) else []
    return data if isinstance(data, list) else []


def save_location_cache(cache_path: Path, locations: list[dict[str, Any]]) -> None:
    """Write the locations cache to disk."""
    payload = {
        "updated_at": datetime.utcnow().isoformat(),
        "count": len(locations),
        "locations": locations,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(__import__("json").dumps(payload, indent=2), encoding="utf-8")


def to_location_options(
    locations: list[dict[str, Any]],
    *,
    location_type: str | None = "Country",
) -> list[LocationOption]:
    """Convert raw locations into sorted CLI options."""
    options: list[LocationOption] = []
    for item in locations:
        if not isinstance(item, dict):
            continue
        if location_type and item.get("location_type") != location_type:
            continue
        code = item.get("location_code")
        name = item.get("location_name")
        if not isinstance(code, int) or not isinstance(name, str):
            continue
        options.append(LocationOption(
            code=code,
            name=name,
            country_iso_code=item.get("country_iso_code"),
            location_type=item.get("location_type"),
        ))
    options.sort(key=lambda opt: (opt.name.lower(), opt.code))
    return options
