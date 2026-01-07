"""
Base class for web search providers.

All search providers implement this interface to allow easy swapping
between Tavily, Google CSE, SearXNG, or any future providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import logging

logger = logging.getLogger(__name__)


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
        Search for product specifications.

        Builds an optimized query for finding product specs.

        Args:
            manufacturer: Product manufacturer
            model_number: Model/part number
            product_name: Optional product name hint

        Returns:
            SearchResponse with results
        """
        # Build search query optimized for product specs
        parts = []
        if manufacturer:
            parts.append(manufacturer)
        if model_number:
            parts.append(model_number)
        if product_name and product_name != model_number:
            parts.append(product_name)
        parts.append("specifications")

        query = " ".join(parts)
        logger.debug(f"Product search query: {query}")

        return await self.search(query, max_results=5, include_content=True)
