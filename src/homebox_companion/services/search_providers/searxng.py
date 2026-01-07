"""
SearXNG Search Provider.

SearXNG is a free, open-source, privacy-respecting metasearch engine.
It can be self-hosted and aggregates results from multiple search engines.

Benefits:
- No API key required (self-hosted)
- Privacy-focused (no tracking)
- Aggregates multiple search engines
- Free and open source

Requires:
- SEARXNG_URL: URL to your SearXNG instance (e.g., https://searx.example.com)

Public instances: https://searx.space
Self-hosting: https://docs.searxng.org
"""

import logging
from typing import Any
from urllib.parse import urlencode, urljoin

import httpx

from homebox_companion.services.debug_logger import debug_log
from .base import BaseSearchProvider, SearchResult, SearchResponse

logger = logging.getLogger(__name__)


class SearXNGSearchProvider(BaseSearchProvider):
    """
    SearXNG metasearch engine provider.

    SearXNG aggregates results from multiple search engines without
    requiring API keys. You can use a public instance or self-host.

    The JSON API must be enabled on the SearXNG instance.
    """

    def __init__(self, instance_url: str | None = None):
        """
        Initialize SearXNG provider.

        Args:
            instance_url: URL to SearXNG instance (e.g., https://searx.example.com)
        """
        self._instance_url = instance_url.rstrip("/") if instance_url else None
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_name(self) -> str:
        return "SearXNG"

    def is_configured(self) -> bool:
        return bool(self._instance_url)

    def set_instance_url(self, url: str) -> None:
        """Update the instance URL."""
        self._instance_url = url.rstrip("/") if url else None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
            )
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
        Search using SearXNG API.

        Args:
            query: Search query
            max_results: Maximum results to return
            include_content: Not used (SearXNG doesn't provide full content)

        Returns:
            SearchResponse with results
        """
        if not self.is_configured():
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error="SearXNG instance URL not configured",
            )

        debug_log("SEARCH_SEARXNG", f"Searching: {query}", {
            "instance_url": self._instance_url,
            "max_results": max_results,
        })

        try:
            client = await self._get_client()

            # SearXNG JSON API endpoint
            params: dict[str, Any] = {
                "q": query,
                "format": "json",
                "categories": "general",
            }

            url = f"{self._instance_url}/search?{urlencode(params)}"

            # Some SearXNG instances require a User-Agent
            headers = {
                "User-Agent": "HomeBox-Companion/1.0",
                "Accept": "application/json",
            }

            response = await client.get(url, headers=headers)

            if response.status_code == 403:
                debug_log("SEARCH_SEARXNG", "Access forbidden - JSON API may be disabled", level="ERROR")
                return SearchResponse(
                    query=query,
                    provider=self.provider_name,
                    error="SearXNG JSON API is disabled on this instance",
                )

            if response.status_code == 429:
                debug_log("SEARCH_SEARXNG", "Rate limit exceeded", level="WARNING")
                return SearchResponse(
                    query=query,
                    provider=self.provider_name,
                    error="SearXNG rate limit exceeded",
                )

            response.raise_for_status()

            # Check if we got JSON or HTML (HTML means JSON API is disabled)
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type:
                debug_log("SEARCH_SEARXNG", "Got HTML response - JSON API may be disabled", level="ERROR")
                return SearchResponse(
                    query=query,
                    provider=self.provider_name,
                    error="SearXNG returned HTML. JSON API may be disabled on this instance.",
                )

            data = response.json()

            results = []
            for item in data.get("results", [])[:max_results]:
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),  # SearXNG uses "content" for snippet
                    content="",  # SearXNG doesn't provide full page content
                    score=item.get("score", 0.0),
                ))

            debug_log("SEARCH_SEARXNG", f"Found {len(results)} results", {
                "query": query,
                "result_count": len(results),
            })

            return SearchResponse(
                query=query,
                results=results,
                total_results=len(results),
                provider=self.provider_name,
            )

        except httpx.ConnectError:
            debug_log("SEARCH_SEARXNG", f"Cannot connect to {self._instance_url}", level="ERROR")
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error=f"Cannot connect to SearXNG instance at {self._instance_url}",
            )
        except httpx.TimeoutException:
            debug_log("SEARCH_SEARXNG", "Request timed out", level="ERROR")
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error="SearXNG search timed out",
            )
        except httpx.HTTPStatusError as e:
            debug_log("SEARCH_SEARXNG", f"HTTP error: {e}", level="ERROR")
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error=f"SearXNG error: {e.response.status_code}",
            )
        except Exception as e:
            logger.error(f"SearXNG search failed: {e}")
            debug_log("SEARCH_SEARXNG", f"Search failed: {e}", level="ERROR")
            return SearchResponse(
                query=query,
                provider=self.provider_name,
                error=str(e),
            )
