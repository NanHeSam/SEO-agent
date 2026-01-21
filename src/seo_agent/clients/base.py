"""Base async HTTP client with retry logic."""

from typing import Any
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


class BaseAsyncClient:
    """Base async HTTP client with retry logic and common configuration."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseAsyncClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client instance."""
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")
        return self._client

    def _get_headers(self) -> dict[str, str]:
        """Get default headers. Override in subclasses for auth headers."""
        return {"Content-Type": "application/json"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request with retry logic."""
        headers = {**self._get_headers(), **kwargs.pop("headers", {})}
        response = await self.client.request(
            method,
            endpoint,
            headers=headers,
            **kwargs,
        )
        response.raise_for_status()
        return response

    async def get(self, endpoint: str, **kwargs: Any) -> httpx.Response:
        """Make a GET request."""
        return await self._request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs: Any) -> httpx.Response:
        """Make a POST request."""
        return await self._request("POST", endpoint, **kwargs)

    async def get_json(self, endpoint: str, **kwargs: Any) -> Any:
        """Make a GET request and return JSON."""
        response = await self.get(endpoint, **kwargs)
        return response.json()

    async def post_json(self, endpoint: str, **kwargs: Any) -> Any:
        """Make a POST request and return JSON."""
        response = await self.post(endpoint, **kwargs)
        return response.json()
