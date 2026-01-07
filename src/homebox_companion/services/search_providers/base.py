"""
Base class for web search providers.

All search providers implement this interface to allow easy swapping
between Tavily, Google CSE, SearXNG, or any future providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class SearchResult:
    """A single search result."""

    title: str
    url: str
    snippet: str
    content: str = ""  # Full content if available (Tavily provides this)
    score: float = 0.0  # Relevance score if available

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "content": self.content,
            "score": self.score,
        }


@dataclass
class SearchResponse:
    """Response from a search query."""

    query: str
    results: list[SearchResult] = field(default_factory=list)
    total_results: int = 0
    provider: str = ""
    error: str | None = None

    @property
    def success(self) -> bool:
        """Whether the search was successful."""
        return self.error is None and len(self.results) > 0

    def get_combined_content(self, max_results: int = 3) -> str:
        """
        Get combined content from top results for AI processing.

        Args:
            max_results: Maximum number of results to include

        Returns:
            Combined text content from search results
        """
        parts = []
        for i, result in enumerate(self.results[:max_results]):
            content = result.content or result.snippet
            if content:
                parts.append(f"Source {i+1}: {result.title}\n{content}\n")
        return "\n".join(parts)


class BaseSearchProvider(ABC):
    """
    Abstract base class for web search providers.

    All search providers must implement:
    - search(): Perform a web search
    - is_configured(): Check if provider has required credentials
    - provider_name: Human-readable provider name
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name of the provider."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if the provider has all required configuration.

        Returns:
            True if provider is ready to use, False otherwise
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
        include_content: bool = True,
    ) -> SearchResponse:
        """
        Perform a web search.

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            include_content: Whether to fetch full page content (if supported)

        Returns:
            SearchResponse with results or error
        """
        pass

    async def search_product(
        self,
        manufacturer: str,
        model_number: str,
        product_name: str = "",
    ) -> SearchResponse:
        """
        Search for product specifications and pricing.

        Performs multiple searches to gather comprehensive product information:
        1. Specifications and features
        2. Pricing (MSRP, retail price)

        Args:
            manufacturer: Product manufacturer
            model_number: Model/part number
            product_name: Optional product name hint

        Returns:
            SearchResponse with combined results from all searches
        """
        # Build base product identifier
        base_parts = []
        if manufacturer:
            base_parts.append(manufacturer)
        if model_number:
            base_parts.append(model_number)

        base_query = " ".join(base_parts)

        # Search queries to run:
        # 1. General specs search
        # 2. General pricing search
        # 3. Site-specific search targeting retailers (avoid Amazon/HD which have aggressive bot protection)
        queries = [
            f"{base_query} specifications features specs",
            f"{base_query} MSRP price retail",
            # Target retailers with less aggressive bot protection
            # Lowes, Menards (home improvement), Digikey, Mouser (electronics), Grainger (industrial)
            f"{base_query} site:lowes.com OR site:digikey.com OR site:mouser.com OR site:grainger.com",
        ]

        # Collect all results
        all_results: list[SearchResult] = []
        seen_urls: set[str] = set()

        for query in queries:
            logger.info(f"Product search query: {query}")
            response = await self.search(query, max_results=3, include_content=True)

            if response.success:
                for result in response.results:
                    # Deduplicate by URL
                    if result.url not in seen_urls:
                        seen_urls.add(result.url)
                        all_results.append(result)

        # Return combined response
        combined_query = f"{base_query} (specs + pricing)"
        return SearchResponse(
            query=combined_query,
            results=all_results[:8],  # Limit to top 8 unique results
            total_results=len(all_results),
            provider=self.provider_name,
        )
