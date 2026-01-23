"""DataForSEO API client for keyword research."""

from typing import Any

import httpx

from seo_agent.clients.base import BaseAsyncClient
from seo_agent.core.workflow_logger import get_logger


class DataForSEOError(RuntimeError):
    """Raised when DataForSEO API returns an error response."""

    def __init__(
        self,
        message: str,
        *,
        operation: str,
        status_code: int | None = None,
        status_message: str | None = None,
        task_errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.status_code = status_code
        self.status_message = status_message
        self.task_errors = task_errors or []


class DataForSEOClient(BaseAsyncClient):
    """Client for DataForSEO API endpoints."""

    BASE_URL = "https://api.dataforseo.com"

    @staticmethod
    def _normalize_number(value: Any, default: int | float = 0) -> int | float:
        if value is None:
            return default
        return value

    def _extract_task_errors(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        task_errors = []
        for task in response.get("tasks", []):
            if task.get("status_code") != 20000:
                task_errors.append({
                    "status_code": task.get("status_code"),
                    "status_message": task.get("status_message"),
                    "error_message": task.get("error_message"),
                    "id": task.get("id"),
                })
        return task_errors

    def _ensure_success(self, operation: str, response: dict[str, Any]) -> None:
        status_code = response.get("status_code")
        status_message = response.get("status_message")
        tasks_error = response.get("tasks_error", 0)
        task_errors = self._extract_task_errors(response)

        if status_code != 20000 or tasks_error or task_errors:
            message = (
                f"DataForSEO API error during {operation}: "
                f"status_code={status_code} status_message={status_message}"
            )
            if task_errors:
                first = task_errors[0]
                message = (
                    f"{message} task_status_code={first.get('status_code')} "
                    f"task_status_message={first.get('status_message')}"
                )

            logger = get_logger()
            if logger:
                logger.log_dataforseo_error(operation, {
                    "status_code": status_code,
                    "status_message": status_message,
                    "tasks_error": tasks_error,
                    "tasks_count": response.get("tasks_count"),
                    "task_errors": task_errors,
                })

            raise DataForSEOError(
                message,
                operation=operation,
                status_code=status_code,
                status_message=status_message,
                task_errors=task_errors,
            )

    def _handle_http_error(self, operation: str, exc: httpx.HTTPStatusError) -> None:
        response = exc.response
        http_status = response.status_code
        http_reason = response.reason_phrase
        details: dict[str, Any] = {
            "http_status": http_status,
            "http_reason": http_reason,
        }

        response_data: dict[str, Any] | None = None
        try:
            response_data = response.json()
            details["response"] = response_data
        except ValueError:
            text = response.text
            details["response_text"] = text[:1000] if text else ""

        data_status_code: int | None = None
        data_status_message: str | None = None
        if response_data:
            data_status_code = response_data.get("status_code")
            data_status_message = response_data.get("status_message")

        status_code = data_status_code if data_status_code is not None else http_status
        status_message = data_status_message if data_status_message and data_status_message != "Ok." else http_reason

        logger = get_logger()
        if logger:
            logger.log_dataforseo_error(operation, details)

        raise DataForSEOError(
            f"DataForSEO HTTP error during {operation}: {http_status} {http_reason}",
            operation=operation,
            status_code=status_code,
            status_message=status_message,
        )

    async def _post_json(self, endpoint: str, *, operation: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self.post(endpoint, **kwargs)
        except httpx.HTTPStatusError as exc:
            self._handle_http_error(operation, exc)
            raise

        data = response.json()
        self._ensure_success(operation, data)
        return data

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

        response = await self._post_json(
            "/v3/dataforseo_labs/google/keyword_suggestions/live",
            json=payload,
            operation="get_keyword_suggestions",
        )

        result = self._extract_keywords(response)

        # Log the API response
        logger = get_logger()
        if logger:
            # Convert list to dict for logging
            response_data = {
                kw["keyword"]: {
                    "search_volume": self._normalize_number(kw.get("search_volume"), 0),
                    "cpc": self._normalize_number(kw.get("cpc"), 0),
                    "competition": self._normalize_number(kw.get("competition"), 0),
                    "competition_level": kw.get("competition_level", ""),
                }
                for kw in result
            }
            logger.log_dataforseo_response(
                operation="get_keyword_suggestions",
                keywords=[seed_keyword],
                response_data=response_data,
            )

        return result

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

        response = await self._post_json(
            "/v3/dataforseo_labs/google/keyword_ideas/live",
            json=payload,
            operation="get_keyword_ideas",
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

        response = await self._post_json(
            "/v3/dataforseo_labs/google/bulk_keyword_difficulty/live",
            json=payload,
            operation="get_bulk_keyword_difficulty",
        )

        result = self._extract_difficulty_data(response)

        # Log the API response
        logger = get_logger()
        if logger:
            logger.log_dataforseo_response(
                operation="get_bulk_keyword_difficulty",
                keywords=keywords,
                response_data=result,
            )

        return result

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

        response = await self._post_json(
            "/v3/keywords_data/google_ads/search_volume/live",
            json=payload,
            operation="get_search_volume",
        )

        result = self._extract_search_volume_data(response)

        # Log the API response
        logger = get_logger()
        if logger:
            logger.log_dataforseo_response(
                operation="get_search_volume",
                keywords=keywords,
                response_data=result,
            )

        return result

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
                    "search_volume": self._normalize_number(item.get("search_volume"), 0),
                    "cpc": self._normalize_number(item.get("cpc"), 0),
                    "competition": self._normalize_number(item.get("competition"), 0),
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
                    "search_volume": self._normalize_number(idea.get("search_volume"), 0),
                    "keyword_difficulty": self._normalize_number(difficulty_info.get("keyword_difficulty"), 0),
                    "cpc": self._normalize_number(idea.get("cpc"), 0),
                    "competition": self._normalize_number(idea.get("competition"), 0),
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
                            "search_volume", self._normalize_number(item.get("search_volume"), 0)
                        ),
                        "cpc": keyword_info.get("keyword_info", {}).get(
                            "cpc", self._normalize_number(item.get("cpc"), 0)
                        ),
                        "competition": keyword_info.get("keyword_info", {}).get(
                            "competition", self._normalize_number(item.get("competition"), 0)
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
                        "keyword_difficulty": self._normalize_number(item.get("keyword_difficulty"), 0),
                    }

        return difficulty_map


def create_dataforseo_client(api_credentials: str) -> DataForSEOClient:
    """Factory function to create a DataForSEO client.

    Args:
        api_credentials: Base64-encoded "login:password" string
    """
    return DataForSEOClient(api_credentials=api_credentials)
