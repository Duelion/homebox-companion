"""
Tavily Search Provider.

Tavily is an AI-optimized search API that provides:
- Clean, extracted content (not just snippets)
- High-quality results optimized for LLM consumption
- Fast response times

Requires: TAVILY_API_KEY or configured in app preferences.
Get your API key at: https://tavily.com
"""

import logging
from typing import Any

import httpx

from homebox_companion.services.debug_logger import debug_log
from .base import BaseSearchProvider, SearchResult, SearchResponse

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


class TavilySearchProvider(BaseSearchProvider):
    """
    Tavily search provider.

    Tavily provides AI-optimized search with clean content extraction,
    making it ideal for enrichment where we need actual product specs.
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize Tavily provider.

        Args:
            api_key: Tavily API key (get one at https://tavily.com)
        """
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_name(self) -> str:
        return "Tavily"

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def set_api_key(self, api_key: str) -> None:
        """Update the API key."""
        self._api_key = api_key

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
        Search using Tavily API.

        Args:
            query: Search query
            max_results: Maximum results (1-10)
            include_content: Include full page content

        Returns:
            SearchResponse with results
        """
        if not self.is_configured():
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error="Tavily API key not configured",
            )

        debug_log("SEARCH_TAVILY", f"Searching: {query}", {
            "max_results": max_results,
            "include_content": include_content,
        })

        try:
            client = await self._get_client()

            payload: dict[str, Any] = {
                "api_key": self._api_key,
                "query": query,
                "max_results": min(max_results, 10),
                "include_answer": False,
                "include_raw_content": include_content,
                "search_depth": "advanced" if include_content else "basic",
            }

            response = await client.post(TAVILY_API_URL, json=payload)

            if response.status_code == 401:
                debug_log("SEARCH_TAVILY", "Invalid API key", level="ERROR")
                return SearchResponse(
                    query=query,
                    provider=self.provider_name,
                    error="Invalid Tavily API key",
                )

            if response.status_code == 429:
                debug_log("SEARCH_TAVILY", "Rate limit exceeded", level="WARNING")
                return SearchResponse(
                    query=query,
                    provider=self.provider_name,
                    error="Tavily rate limit exceeded. Please try again later.",
                )

            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", "")[:500],  # Tavily's "content" is the snippet
                    content=item.get("raw_content", ""),  # Full content if requested
                    score=item.get("score", 0.0),
                ))

            debug_log("SEARCH_TAVILY", f"Found {len(results)} results", {
                "query": query,
                "result_count": len(results),
            })

            return SearchResponse(
                query=query,
                results=results,
                total_results=len(results),
                provider=self.provider_name,
            )

        except httpx.TimeoutException:
            debug_log("SEARCH_TAVILY", "Request timed out", level="ERROR")
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error="Tavily search timed out",
            )
        except httpx.HTTPStatusError as e:
            debug_log("SEARCH_TAVILY", f"HTTP error: {e}", level="ERROR")
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error=f"Tavily API error: {e.response.status_code}",
            )
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            debug_log("SEARCH_TAVILY", f"Search failed: {e}", level="ERROR")
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error=str(e),
            )
