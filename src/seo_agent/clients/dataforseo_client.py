"""DataForSEO API client for keyword research."""

from typing import Any

from seo_agent.clients.base import BaseAsyncClient


class DataForSEOClient(BaseAsyncClient):
    """Client for DataForSEO API endpoints."""

    BASE_URL = "https://api.dataforseo.com"

    def __init__(
        self,
        api_credentials: str,
        timeout: float = 60.0,
    ):
        """
        Initialize DataForSEO client.

        Args:
            api_credentials: Base64-encoded "login:password" string
            timeout: Request timeout in seconds
        """
        super().__init__(base_url=self.BASE_URL, timeout=timeout)
        self._auth_token = api_credentials

    def _get_headers(self) -> dict[str, str]:
        """Get headers with Basic Auth."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Basic {self._auth_token}",
        }

    async def get_keyword_suggestions(
        self,
        seed_keyword: str,
        location_code: int = 2840,  # United States
        language_code: str = "en",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get keyword suggestions based on a seed keyword.

        Uses: POST /v3/dataforseo_labs/google/keyword_suggestions/live
        """
        payload = [
            {
                "keyword": seed_keyword,
                "location_code": location_code,
                "language_code": language_code,
                "limit": limit,
                "include_seed_keyword": True,
            }
        ]

        response = await self.post_json(
            "/v3/dataforseo_labs/google/keyword_suggestions/live",
            json=payload,
        )

        return self._extract_keywords(response)

    async def get_keyword_ideas(
        self,
        keywords: list[str],
        location_code: int = 2840,
        language_code: str = "en",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get keyword ideas based on multiple keywords.

        Uses: POST /v3/dataforseo_labs/google/keyword_ideas/live
        """
        payload = [
            {
                "keywords": keywords,
                "location_code": location_code,
                "language_code": language_code,
                "limit": limit,
            }
        ]

        response = await self.post_json(
            "/v3/dataforseo_labs/google/keyword_ideas/live",
            json=payload,
        )

        return self._extract_keywords(response)

    async def get_bulk_keyword_difficulty(
        self,
        keywords: list[str],
        location_code: int = 2840,
        language_code: str = "en",
    ) -> dict[str, dict[str, Any]]:
        """
        Get keyword difficulty scores for multiple keywords.

        Uses: POST /v3/dataforseo_labs/google/bulk_keyword_difficulty/live
        """
        payload = [
            {
                "keywords": keywords,
                "location_code": location_code,
                "language_code": language_code,
            }
        ]

        response = await self.post_json(
            "/v3/dataforseo_labs/google/bulk_keyword_difficulty/live",
            json=payload,
        )

        return self._extract_difficulty_data(response)

    async def get_search_volume(
        self,
        keywords: list[str],
        location_code: int = 2840,
        language_code: str = "en",
    ) -> dict[str, dict[str, Any]]:
        """
        Get search volume for exact keywords.

        Uses: POST /v3/keywords_data/google_ads/search_volume/live
        """
        payload = [
            {
                "keywords": keywords,
                "location_code": location_code,
                "language_code": language_code,
            }
        ]

        response = await self.post_json(
            "/v3/keywords_data/google_ads/search_volume/live",
            json=payload,
        )

        return self._extract_search_volume_data(response)

    def _extract_search_volume_data(
        self, response: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Extract search volume data from API response."""
        volume_map = {}
        tasks = response.get("tasks", [])

        for task in tasks:
            if task.get("status_code") != 20000:
                continue

            results = task.get("result", [])
            for item in results:
                keyword = item.get("keyword", "").lower()
                volume_map[keyword] = {
                    "search_volume": item.get("search_volume", 0),
                    "cpc": item.get("cpc", 0),
                    "competition": item.get("competition", 0),
                    "competition_level": item.get("competition_level", ""),
                }

        return volume_map

    async def get_keyword_metrics(
        self,
        keywords: list[str],
        location_code: int = 2840,
        language_code: str = "en",
    ) -> list[dict[str, Any]]:
        """
        Get comprehensive metrics for keywords including volume and KD.

        Combines keyword suggestions with bulk difficulty data.
        """
        # Get search volume from keyword ideas
        ideas_response = await self.get_keyword_ideas(
            keywords=keywords,
            location_code=location_code,
            language_code=language_code,
            limit=len(keywords) * 2,  # Get extra to ensure we find all
        )

        # Get keyword difficulty
        difficulty_data = await self.get_bulk_keyword_difficulty(
            keywords=keywords,
            location_code=location_code,
            language_code=language_code,
        )

        # Merge the data
        keyword_metrics = []
        for idea in ideas_response:
            kw = idea.get("keyword", "").lower()
            if kw in [k.lower() for k in keywords]:
                difficulty_info = difficulty_data.get(kw, {})
                keyword_metrics.append({
                    "keyword": idea.get("keyword"),
                    "search_volume": idea.get("search_volume", 0),
                    "keyword_difficulty": difficulty_info.get("keyword_difficulty", 0),
                    "cpc": idea.get("cpc", 0),
                    "competition": idea.get("competition", 0),
                    "competition_level": idea.get("competition_level", ""),
                })

        return keyword_metrics

    def _extract_keywords(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract keyword data from API response."""
        keywords = []
        tasks = response.get("tasks", [])

        for task in tasks:
            if task.get("status_code") != 20000:
                continue

            results = task.get("result", [])
            for result in results:
                items = result.get("items", [])
                for item in items:
                    keyword_info = item.get("keyword_data", item)
                    keywords.append({
                        "keyword": keyword_info.get("keyword", item.get("keyword", "")),
                        "search_volume": keyword_info.get("keyword_info", {}).get(
                            "search_volume", item.get("search_volume", 0)
                        ),
                        "cpc": keyword_info.get("keyword_info", {}).get(
                            "cpc", item.get("cpc", 0)
                        ),
                        "competition": keyword_info.get("keyword_info", {}).get(
                            "competition", item.get("competition", 0)
                        ),
                        "competition_level": keyword_info.get("keyword_info", {}).get(
                            "competition_level", item.get("competition_level", "")
                        ),
                    })

        return keywords

    def _extract_difficulty_data(
        self, response: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Extract keyword difficulty data from API response."""
        difficulty_map = {}
        tasks = response.get("tasks", [])

        for task in tasks:
            if task.get("status_code") != 20000:
                continue

            results = task.get("result", [])
            for result in results:
                items = result.get("items", [])
                for item in items:
                    keyword = item.get("keyword", "").lower()
                    difficulty_map[keyword] = {
                        "keyword_difficulty": item.get("keyword_difficulty", 0),
                    }

        return difficulty_map


def create_dataforseo_client(api_credentials: str) -> DataForSEOClient:
    """Factory function to create a DataForSEO client.

    Args:
        api_credentials: Base64-encoded "login:password" string
    """
    return DataForSEOClient(api_credentials=api_credentials)
