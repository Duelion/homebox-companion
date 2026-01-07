"""
Google Custom Search Engine (CSE) Provider.

Google Custom Search provides:
- Access to Google's search index
- Customizable search scope
- JSON API for programmatic access

Requires:
- GOOGLE_CSE_API_KEY: API key from Google Cloud Console
- GOOGLE_CSE_ID: Search Engine ID from Programmable Search Engine

Setup:
1. Create a project at https://console.cloud.google.com
2. Enable "Custom Search API"
3. Create credentials (API Key)
4. Create a search engine at https://programmablesearchengine.google.com
5. Get the Search Engine ID (cx parameter)
"""

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from homebox_companion.services.debug_logger import debug_log
from .base import BaseSearchProvider, SearchResult, SearchResponse

logger = logging.getLogger(__name__)

GOOGLE_CSE_API_URL = "https://www.googleapis.com/customsearch/v1"


class GoogleCSESearchProvider(BaseSearchProvider):
    """
    Google Custom Search Engine provider.

    Uses Google's Programmable Search Engine API to perform web searches.
    Provides high-quality results from Google's index.

    Note: Google CSE has a free tier of 100 queries/day, then $5 per 1000 queries.
    """

    def __init__(
        self,
        api_key: str | None = None,
        search_engine_id: str | None = None,
    ):
        """
        Initialize Google CSE provider.

        Args:
            api_key: Google Cloud API key
            search_engine_id: Programmable Search Engine ID (cx)
        """
        self._api_key = api_key
        self._search_engine_id = search_engine_id
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_name(self) -> str:
        return "Google Custom Search"

    def is_configured(self) -> bool:
        return bool(self._api_key and self._search_engine_id)

    def set_credentials(self, api_key: str, search_engine_id: str) -> None:
        """Update credentials."""
        self._api_key = api_key
        self._search_engine_id = search_engine_id

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(
        self,
        query: str,
        max_results: int = 5,
        include_content: bool = True,
    ) -> SearchResponse:
        """
        Search using Google Custom Search API.

        Args:
            query: Search query
            max_results: Maximum results (1-10)
            include_content: Not used (Google CSE doesn't provide full content)

        Returns:
            SearchResponse with results
        """
        if not self.is_configured():
            missing = []
            if not self._api_key:
                missing.append("API key")
            if not self._search_engine_id:
                missing.append("Search Engine ID")
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error=f"Google CSE not configured: missing {', '.join(missing)}",
            )

        debug_log("SEARCH_GOOGLE", f"Searching: {query}", {
            "max_results": max_results,
        })

        try:
            client = await self._get_client()

            params: dict[str, Any] = {
                "key": self._api_key,
                "cx": self._search_engine_id,
                "q": query,
                "num": min(max_results, 10),  # Google CSE max is 10 per request
            }

            url = f"{GOOGLE_CSE_API_URL}?{urlencode(params)}"
            response = await client.get(url)

            if response.status_code == 400:
                data = response.json()
                error_msg = data.get("error", {}).get("message", "Bad request")
                debug_log("SEARCH_GOOGLE", f"Bad request: {error_msg}", level="ERROR")
                return SearchResponse(
                    query=query,
                    provider=self.provider_name,
                    error=f"Google CSE error: {error_msg}",
                )

            if response.status_code == 403:
                debug_log("SEARCH_GOOGLE", "Invalid API key or quota exceeded", level="ERROR")
                return SearchResponse(
                    query=query,
                    provider=self.provider_name,
                    error="Google CSE: Invalid API key or daily quota exceeded",
                )

            if response.status_code == 429:
                debug_log("SEARCH_GOOGLE", "Rate limit exceeded", level="WARNING")
                return SearchResponse(
                    query=query,
                    provider=self.provider_name,
                    error="Google CSE rate limit exceeded",
                )

            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("items", []):
                # Google CSE provides title, link, and snippet
                # It doesn't provide full page content
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    content="",  # Google CSE doesn't provide full content
                    score=0.0,  # Google doesn't provide relevance scores
                ))

            total = int(data.get("searchInformation", {}).get("totalResults", 0))

            debug_log("SEARCH_GOOGLE", f"Found {len(results)} results", {
                "query": query,
                "result_count": len(results),
                "total_results": total,
            })

            return SearchResponse(
                query=query,
                results=results,
                total_results=total,
                provider=self.provider_name,
            )

        except httpx.TimeoutException:
            debug_log("SEARCH_GOOGLE", "Request timed out", level="ERROR")
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error="Google CSE search timed out",
            )
        except httpx.HTTPStatusError as e:
            debug_log("SEARCH_GOOGLE", f"HTTP error: {e}", level="ERROR")
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error=f"Google CSE API error: {e.response.status_code}",
            )
        except Exception as e:
            logger.error(f"Google CSE search failed: {e}")
            debug_log("SEARCH_GOOGLE", f"Search failed: {e}", level="ERROR")
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error=str(e),
            )
