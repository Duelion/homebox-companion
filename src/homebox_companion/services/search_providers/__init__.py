"""
Web Search Providers for Enrichment.

Provides abstraction for multiple web search backends:
- Tavily: AI-optimized search API
- Google Custom Search: Google's programmable search
- SearXNG: Self-hosted meta search engine (no API key needed)
"""

from .base import BaseSearchProvider, SearchResult, SearchResponse
from .tavily import TavilySearchProvider
from .google_cse import GoogleCSESearchProvider
from .searxng import SearXNGSearchProvider

__all__ = [
    "BaseSearchProvider",
    "SearchResult",
    "SearchResponse",
    "TavilySearchProvider",
    "GoogleCSESearchProvider",
    "SearXNGSearchProvider",
]
