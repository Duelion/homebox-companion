"""
Enrichment Service - AI-powered product specification lookup.

This service enhances AI-extracted product data with detailed specifications
using either:
1. Web search (Tavily, Google CSE, or SearXNG) + AI parsing
2. AI training knowledge alone (fallback)

The enrichment flow:
1. If web search is configured, search for product specifications
2. Parse search results with AI to extract structured data
3. Fall back to AI-only if search fails or isn't configured

Privacy considerations:
- Disabled by default (opt-in)
- Only manufacturer and model number are sent
- Serial numbers are NEVER sent externally
- Results are cached locally to minimize API calls
- Web search is optional - works without external APIs
"""

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

import httpx
from loguru import logger

if TYPE_CHECKING:
    from homebox_companion.providers.base import BaseProvider

from homebox_companion.services.debug_logger import debug_log
from homebox_companion.services.search_providers import (
    BaseSearchProvider,
    SearchResponse,
    SearchResult,
    TavilySearchProvider,
    GoogleCSESearchProvider,
    SearXNGSearchProvider,
)


# =============================================================================
# URL CONTENT FETCHER
# =============================================================================

class URLContentFetcher:
    """Fetches and extracts content from retailer URLs."""

    # Built-in retailer domains that typically have product prices
    DEFAULT_RETAILER_DOMAINS = {
        # Home improvement
        "homedepot.com",
        "lowes.com",
        "menards.com",
        "acehardware.com",
        "northerntool.com",
        # General retail
        "amazon.com",
        "walmart.com",
        "target.com",
        "bestbuy.com",
        "costco.com",
        "samsclub.com",
        # Tools
        "grainger.com",
        "zoro.com",
        "toolnut.com",
        "cpooutlets.com",
        "acmetools.com",
        # Electronics
        "digikey.com",
        "mouser.com",
        "newark.com",
        "arrow.com",
        "adafruit.com",
        "sparkfun.com",
        "microcenter.com",
        "newegg.com",
        "bhphotovideo.com",
        # Industrial/specialty
        "mcmaster.com",
        "mscdirect.com",
        "uline.com",
        # Home goods / appliances
        "wayfair.com",
        "ikea.com",
        "williams-sonoma.com",
        "crateandbarrel.com",
        "bedbathandbeyond.com",
        "appliancesconnection.com",
        "ajmadison.com",
    }

    def __init__(self, timeout: float = 10.0, custom_domains: list[str] | None = None):
        """
        Initialize the URL content fetcher.

        Args:
            timeout: Request timeout in seconds
            custom_domains: Additional retailer domains to recognize
        """
        self.timeout = timeout
        # Combine default domains with custom ones
        self._retailer_domains = set(self.DEFAULT_RETAILER_DOMAINS)
        if custom_domains:
            # Normalize custom domains (lowercase, strip whitespace)
            normalized = {d.lower().strip() for d in custom_domains if d.strip()}
            self._retailer_domains.update(normalized)
            if normalized:
                logger.info(f"Added {len(normalized)} custom retailer domains")

    def is_retailer_url(self, url: str) -> bool:
        """Check if URL is from a known retailer."""
        url_lower = url.lower()
        return any(domain in url_lower for domain in self._retailer_domains)

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags and extract text content."""
        # Remove script and style blocks
        html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'")
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_price_context(self, text: str, window: int = 200) -> str:
        """Extract text around price mentions."""
        # Find price patterns - support multiple formats:
        # $199.00, $199, USD 199.00, 199.00 USD, €199, £199
        price_patterns = [
            r'\$[\d,]+\.?\d*',           # $199.00
            r'USD\s*[\d,]+\.?\d*',        # USD 199.00
            r'[\d,]+\.?\d*\s*USD',        # 199.00 USD
            r'€[\d,]+\.?\d*',             # €199.00
            r'£[\d,]+\.?\d*',             # £199.00
            r'(?:price|cost|msrp)[:\s]*[\d,]+\.?\d*',  # price: 199.00
        ]

        all_matches = []
        for pattern in price_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            all_matches.extend(matches)

        if not all_matches:
            return ""

        # Sort by position and deduplicate overlapping matches
        all_matches.sort(key=lambda m: m.start())

        # Get context around each price mention
        contexts = []
        for match in all_matches[:5]:  # Limit to first 5 prices
            start = max(0, match.start() - window)
            end = min(len(text), match.end() + window)
            context = text[start:end].strip()
            if context and context not in contexts:
                contexts.append(context)

        return "\n---\n".join(contexts)

    async def fetch_url_content(self, url: str) -> str | None:
        """Fetch and extract text content from a URL."""
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                # Enable cookies to handle session-based bot protection
                cookies={},
            ) as client:
                headers = {
                    # Use a realistic browser User-Agent
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0",
                }
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                # Only process HTML
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    logger.debug(f"Skipping non-HTML content: {content_type}")
                    return None

                html = response.text
                logger.info(f"Fetched {len(html)} bytes of HTML from {url[:60]}...")

                text = self._strip_html(html)
                logger.info(f"Stripped to {len(text)} chars of text")
                # Log a preview of the text for debugging
                logger.debug(f"Text preview: {text[:500]}...")

                # Extract price context for efficiency
                price_context = self._extract_price_context(text)
                if price_context:
                    logger.info(f"Found price context: {len(price_context)} chars with prices")
                    return price_context

                # If no prices found in text, try to find JSON-LD structured data
                # Many retailers embed price in JSON-LD schema
                json_ld_match = re.search(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
                if json_ld_match:
                    json_ld_content = json_ld_match.group(1).strip()
                    # Look for price patterns in the JSON-LD
                    price_in_json = re.search(r'"price"[:\s]*["\']?([\d,.]+)["\']?', json_ld_content)
                    if price_in_json:
                        logger.info(f"Found price in JSON-LD structured data: ${price_in_json.group(1)}")
                        return f"Product price from structured data: ${price_in_json.group(1)}\n\n{text[:2000]}"

                # Return page content even without explicit prices
                # The AI might still extract useful specs
                if len(text) > 100:
                    logger.info(f"No prices found in text, returning {min(len(text), 2000)} chars anyway")
                    return text[:2000]

                logger.warning(f"Page content too short after stripping: {len(text)} chars")
                return None

        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP {e.response.status_code} fetching {url[:60]}")
            return None
        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching {url[:60]}")
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch {url[:60]}: {type(e).__name__}: {e}")
            return None

    async def fetch_retailer_content(
        self,
        search_results: list[SearchResult],
        max_urls: int = 2,
    ) -> str:
        """
        Fetch content from retailer URLs in search results.

        Args:
            search_results: List of search results to check
            max_urls: Maximum number of URLs to fetch

        Returns:
            Combined content from retailer pages
        """
        # Find retailer URLs
        retailer_urls = []
        for result in search_results:
            is_retailer = self.is_retailer_url(result.url)
            logger.debug(f"URL check: {result.url[:60]} -> retailer={is_retailer}")
            if is_retailer:
                retailer_urls.append(result.url)
                if len(retailer_urls) >= max_urls:
                    break

        if not retailer_urls:
            # Log the actual URLs we received to help debugging
            all_urls = [r.url for r in search_results[:5]]
            logger.info(f"No retailer URLs found in {len(search_results)} results. URLs: {all_urls}")
            return ""

        logger.info(f"Fetching content from {len(retailer_urls)} retailer URLs")

        # Fetch URLs in parallel
        tasks = [self.fetch_url_content(url) for url in retailer_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine successful results
        contents = []
        for url, result in zip(retailer_urls, results):
            if isinstance(result, str) and result:
                logger.info(f"Fetched {len(result)} chars from {url[:50]}...")
                contents.append(f"From {url}:\n{result}")
            elif isinstance(result, Exception):
                logger.debug(f"Failed to fetch {url}: {result}")

        return "\n\n".join(contents)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EnrichmentResult:
    """Result of product enrichment lookup."""

    enriched: bool
    source: str
    name: str
    description: str
    features: list[str] = field(default_factory=list)
    msrp: float | None = None
    release_year: int | None = None
    category: str = ""
    additional_specs: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnrichmentResult":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def empty(cls, name: str = "") -> "EnrichmentResult":
        """Create an empty (not enriched) result."""
        return cls(
            enriched=False,
            source="none",
            name=name,
            description="",
            features=[],
            msrp=None,
            release_year=None,
            category="",
            additional_specs={},
            confidence=0.0,
        )


class EnrichmentCache:
    """File-based cache for enrichment results."""

    def __init__(self, cache_dir: Path, ttl_seconds: int = 86400):
        """
        Initialize cache.

        Args:
            cache_dir: Directory to store cache files
            ttl_seconds: Time-to-live in seconds (default: 24 hours)
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds

    def _get_cache_key(self, manufacturer: str, model_number: str) -> str:
        """Generate cache key from product identifiers."""
        key = f"{manufacturer}:{model_number}".lower().strip()
        return hashlib.md5(key.encode()).hexdigest()

    def get(self, manufacturer: str, model_number: str) -> EnrichmentResult | None:
        """Get cached enrichment result."""
        cache_key = self._get_cache_key(manufacturer, model_number)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        # Check TTL
        if time.time() - cache_file.stat().st_mtime > self.ttl:
            cache_file.unlink()
            logger.debug(f"Cache expired for {manufacturer} {model_number}")
            return None

        try:
            data = json.loads(cache_file.read_text())
            logger.debug(f"Cache hit for {manufacturer} {model_number}")
            return EnrichmentResult.from_dict(data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to read cache: {e}")
            cache_file.unlink()
            return None

    def set(
        self, manufacturer: str, model_number: str, result: EnrichmentResult
    ) -> None:
        """Cache enrichment result."""
        cache_key = self._get_cache_key(manufacturer, model_number)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            cache_file.write_text(json.dumps(result.to_dict(), indent=2))
            logger.debug(f"Cached result for {manufacturer} {model_number}")
        except OSError as e:
            logger.warning(f"Failed to write cache: {e}")

    def clear(self) -> int:
        """Clear all cache entries. Returns count of cleared entries."""
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except OSError:
                pass
        return count


class EnrichmentParser:
    """Utility class to parse and normalize enrichment data."""

    @staticmethod
    def extract_features(text: str) -> list[str]:
        """Extract feature bullet points from description text."""
        features = []

        # Look for common patterns
        patterns = [
            r"•\s*(.+?)(?=•|$)",  # Bullet points
            r"-\s+(.+?)(?=\n-|\n\n|$)",  # Dashes
            r"\*\s+(.+?)(?=\n\*|\n\n|$)",  # Asterisks
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
            for match in matches:
                cleaned = match.strip()
                if cleaned and len(cleaned) > 5 and len(cleaned) < 200:
                    features.append(cleaned)

        # Deduplicate while preserving order
        seen = set()
        unique_features = []
        for f in features:
            if f.lower() not in seen:
                seen.add(f.lower())
                unique_features.append(f)

        return unique_features[:10]  # Limit to 10 features

    @staticmethod
    def extract_price(text: str) -> float | None:
        """Extract price from text."""
        patterns = [
            r"MSRP[:\s]*\$?([0-9,]+(?:\.[0-9]{2})?)",
            r"(?:retail|list)\s+price[:\s]*\$?([0-9,]+(?:\.[0-9]{2})?)",
            r"\$([0-9,]+(?:\.[0-9]{2})?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(",", "")
                try:
                    price = float(price_str)
                    # Sanity check - price should be reasonable
                    if 1 <= price <= 100000:
                        return price
                except ValueError:
                    continue

        return None

    @staticmethod
    def extract_year(text: str) -> int | None:
        """Extract release year from text."""
        # Look for 4-digit years in reasonable range (2000-2030)
        matches = re.findall(r"\b(20[0-3][0-9])\b", text)
        if matches:
            # Return most recent plausible year
            current_year = 2026
            years = [int(y) for y in matches if int(y) <= current_year]
            return max(years) if years else None
        return None

    @staticmethod
    def categorize_product(manufacturer: str, model_number: str, name: str) -> str:
        """Determine product category from available info."""
        text = f"{manufacturer} {model_number} {name}".lower()

        categories = {
            "Television": ["tv", "television", "oled", "qled", "lcd", "led tv"],
            "Computer": ["laptop", "desktop", "pc", "computer", "notebook", "macbook"],
            "Phone": ["phone", "iphone", "galaxy", "pixel", "smartphone"],
            "Tablet": ["tablet", "ipad", "surface", "tab"],
            "Audio": ["speaker", "soundbar", "headphone", "earbuds", "receiver", "airpods"],
            "Camera": ["camera", "dslr", "mirrorless", "camcorder", "gopro"],
            "Appliance": ["refrigerator", "washer", "dryer", "dishwasher", "oven", "microwave"],
            "Gaming": ["playstation", "xbox", "nintendo", "console", "gaming"],
            "Network": ["router", "modem", "switch", "access point", "wifi", "mesh"],
            "Tool": ["drill", "saw", "driver", "sander", "grinder", "dewalt", "makita", "milwaukee"],
            "Monitor": ["monitor", "display", "screen"],
        }

        for category, keywords in categories.items():
            if any(kw in text for kw in keywords):
                return category

        return "Other"


class EnrichmentService:
    """
    Service to enrich product data using web search and/or AI.

    Enrichment modes:
    1. Web search + AI parsing (recommended): Search for product specs, then
       use AI to extract structured data from the results.
    2. AI-only (fallback): Use AI's training knowledge directly.

    Supported search providers:
    - Tavily: AI-optimized search with clean content extraction
    - Google CSE: Google's programmable search engine
    - SearXNG: Self-hosted metasearch (no API key needed)
    """

    # Prompt for AI-only enrichment (no web search)
    ENRICHMENT_PROMPT = """You are a product specification expert. Given a manufacturer and model number, provide detailed product information from your knowledge.

Respond in JSON format with these fields:
{{
  "name": "Full official product name",
  "description": "2-3 sentence product description",
  "features": ["Feature 1", "Feature 2", ...],
  "msrp": 999.99,
  "release_year": 2023,
  "category": "Product category"
}}

Rules:
- Only include information you are confident about
- Set msrp to null if unknown
- Set release_year to null if unknown
- Features should be specific specs (e.g., "4K resolution", "20W speakers")
- Keep features list to 5-8 items maximum
- If you don't recognize this product, return {{"name": "", "enriched": false}}

Product to look up:
Manufacturer: {manufacturer}
Model: {model_number}
{hint}

Respond with ONLY the JSON, no other text."""

    # Prompt for parsing web search results
    WEB_SEARCH_PARSE_PROMPT = """You are a product specification expert. Extract detailed product information from the following web search results.

Respond in JSON format with these fields:
{{
  "name": "Full official product name",
  "description": "2-3 sentence product description",
  "features": ["Feature 1", "Feature 2", ...],
  "msrp": 999.99,
  "release_year": 2023,
  "category": "Product category"
}}

Rules:
- Extract only factual information found in the search results
- For msrp: Look for prices like "$159.00", "MSRP: $199", "Price: 149.99", etc.
  - Use the MSRP/list price if available, otherwise use the most common retail price
  - Extract just the numeric value (e.g., 159.00 not "$159.00")
  - Set to null ONLY if no price is mentioned anywhere in the results
- Set release_year to null if not found
- Features should be specific specs found in the results (power, speed, dimensions, etc.)
- Keep features list to 5-8 items maximum
- If the search results don't contain useful product information, return {{"name": "", "enriched": false}}

Product being searched:
Manufacturer: {manufacturer}
Model: {model_number}

Web search results:
{search_content}

Respond with ONLY the JSON, no other text."""

    def __init__(
        self,
        cache_dir: Path,
        ai_provider: "BaseProvider | None" = None,
        cache_ttl: int = 86400,
    ):
        """
        Initialize enrichment service.

        Args:
            cache_dir: Directory for caching results
            ai_provider: AI provider instance (same one used for detection)
            cache_ttl: Cache time-to-live in seconds (default: 24 hours)
        """
        self.cache = EnrichmentCache(cache_dir / "enrichment_cache", cache_ttl)
        self.ai_provider = ai_provider
        self._search_provider: BaseSearchProvider | None = None
        self._custom_retailer_domains: list[str] = []

    def set_provider(self, provider: "BaseProvider") -> None:
        """Set or update the AI provider."""
        self.ai_provider = provider

    def set_custom_retailer_domains(self, domains: list[str]) -> None:
        """Set custom retailer domains for price fetching."""
        self._custom_retailer_domains = domains
        if domains:
            logger.info(f"Set {len(domains)} custom retailer domains")

    def configure_search_provider(
        self,
        provider_type: str,
        tavily_api_key: str | None = None,
        google_api_key: str | None = None,
        google_engine_id: str | None = None,
        searxng_url: str | None = None,
    ) -> None:
        """
        Configure the web search provider.

        Args:
            provider_type: One of 'none', 'tavily', 'google_cse', 'searxng'
            tavily_api_key: API key for Tavily
            google_api_key: API key for Google CSE
            google_engine_id: Search Engine ID for Google CSE
            searxng_url: URL for SearXNG instance
        """
        if provider_type == "tavily" and tavily_api_key:
            self._search_provider = TavilySearchProvider(api_key=tavily_api_key)
            logger.info("Configured Tavily search provider")
        elif provider_type == "google_cse" and google_api_key and google_engine_id:
            self._search_provider = GoogleCSESearchProvider(
                api_key=google_api_key,
                search_engine_id=google_engine_id,
            )
            logger.info("Configured Google CSE search provider")
        elif provider_type == "searxng" and searxng_url:
            self._search_provider = SearXNGSearchProvider(instance_url=searxng_url)
            logger.info(f"Configured SearXNG search provider: {searxng_url}")
        else:
            self._search_provider = None
            if provider_type != "none":
                logger.warning(f"Search provider '{provider_type}' not configured - missing credentials")

    @property
    def search_provider(self) -> BaseSearchProvider | None:
        """Get the configured search provider, if any."""
        return self._search_provider

    @property
    def has_search_provider(self) -> bool:
        """Check if a search provider is configured and ready."""
        return self._search_provider is not None and self._search_provider.is_configured()

    async def enrich(
        self,
        manufacturer: str,
        model_number: str,
        product_name: str = "",
    ) -> EnrichmentResult:
        """
        Enrich product data with detailed specifications.

        Enrichment strategy:
        1. Check cache first
        2. If web search is configured, use it + AI parsing
        3. Fall back to AI-only if search fails or not configured

        Args:
            manufacturer: Product manufacturer
            model_number: Model/part number
            product_name: Optional product name hint

        Returns:
            EnrichmentResult with detailed specs
        """
        debug_log("ENRICHMENT", "enrich() called", {
            "manufacturer": manufacturer,
            "model_number": model_number,
            "product_name": product_name,
            "has_search_provider": self.has_search_provider,
        })

        # Must have model number to enrich
        if not model_number or not model_number.strip():
            logger.debug("No model number provided, skipping enrichment")
            debug_log("ENRICHMENT", "Skipping - no model number provided", level="DEBUG")
            return EnrichmentResult.empty(product_name)

        # Must have AI provider
        if not self.ai_provider:
            logger.warning("No AI provider configured for enrichment")
            debug_log("ENRICHMENT", "No AI provider configured", level="WARNING")
            return EnrichmentResult.empty(product_name)

        model_number = model_number.strip()
        manufacturer = (manufacturer or "").strip()

        # Check cache first
        cached = self.cache.get(manufacturer, model_number)
        if cached is not None:
            logger.info(f"Enrichment cache hit for {manufacturer} {model_number}: enriched={cached.enriched}")
            debug_log("ENRICHMENT", "Cache hit", {
                "manufacturer": manufacturer,
                "model_number": model_number,
                "enriched": cached.enriched,
                "source": cached.source,
            })
            return cached

        logger.info(f"Enrichment cache miss for {manufacturer} {model_number}, will query AI")

        # Try web search first if configured
        result: EnrichmentResult | None = None
        if self.has_search_provider:
            logger.info(f"Using web search for {manufacturer} {model_number}")
            debug_log("ENRICHMENT", f"Starting web search enrichment via {self._search_provider.provider_name}")
            result = await self._web_search_enrich(manufacturer, model_number, product_name)

            if result and result.enriched:
                debug_log("ENRICHMENT", "Web search enrichment successful", {
                    "source": result.source,
                    "confidence": result.confidence,
                })
            else:
                debug_log("ENRICHMENT", "Web search didn't return useful results, falling back to AI-only")
                result = None  # Fall through to AI-only

        # Fall back to AI-only enrichment
        if result is None:
            logger.info(f"Using AI-only enrichment for {manufacturer} {model_number}")
            debug_log("ENRICHMENT", f"Starting AI-only enrichment for {manufacturer} {model_number}")
            result = await self._ai_enrich(manufacturer, model_number, product_name)

        debug_log("ENRICHMENT", "Enrichment complete", {
            "enriched": result.enriched,
            "confidence": result.confidence,
            "source": result.source,
            "has_description": bool(result.description),
            "feature_count": len(result.features),
        })

        # Cache result (even if not enriched, to avoid repeated failed lookups)
        self.cache.set(manufacturer, model_number, result)

        return result

    async def _web_search_enrich(
        self,
        manufacturer: str,
        model_number: str,
        product_name: str,
    ) -> EnrichmentResult | None:
        """
        Enrich using web search + AI parsing.

        Args:
            manufacturer: Product manufacturer
            model_number: Model/part number
            product_name: Optional product name hint

        Returns:
            EnrichmentResult if successful, None to fall back to AI-only
        """
        if not self._search_provider or not self.ai_provider:
            logger.warning("Web search skipped: no search provider or AI provider")
            return None

        try:
            # Search for product specifications
            logger.info(f"Calling {self._search_provider.provider_name} for: {manufacturer} {model_number}")
            search_response = await self._search_provider.search_product(
                manufacturer=manufacturer,
                model_number=model_number,
                product_name=product_name,
            )

            if not search_response.success:
                logger.warning(f"Web search failed: {search_response.error}")
                debug_log("ENRICHMENT", f"Web search failed: {search_response.error}", level="WARNING")
                return None

            if not search_response.results:
                logger.info("Web search returned no results")
                debug_log("ENRICHMENT", "Web search returned no results")
                return None

            # Get combined content from search snippets
            search_content = search_response.get_combined_content(max_results=5)

            # Log search results with full snippets to help debug price extraction
            logger.info(f"Web search returned {len(search_response.results)} results, snippet content: {len(search_content)} chars")
            for i, result in enumerate(search_response.results[:5]):
                # Log full snippet at INFO level to see if prices are in search results
                logger.info(f"  Result {i+1}: {result.url[:60]}")
                logger.info(f"    Title: {result.title}")
                logger.info(f"    Snippet: {result.snippet[:200]}")

            # Fetch actual page content from retailer URLs to get prices
            content_fetcher = URLContentFetcher(
                timeout=10.0,
                custom_domains=self._custom_retailer_domains,
            )
            retailer_content = await content_fetcher.fetch_retailer_content(
                search_response.results,
                max_urls=2,
            )

            # Combine snippets with retailer page content
            combined_content = search_content
            if retailer_content:
                logger.info(f"Adding {len(retailer_content)} chars of retailer page content")
                combined_content = f"{search_content}\n\n--- Retailer Page Content ---\n{retailer_content}"

            if not combined_content or len(combined_content) < 50:
                debug_log("ENRICHMENT", "Web search content too short to be useful")
                return None

            debug_log("ENRICHMENT", "Parsing web search results with AI", {
                "result_count": len(search_response.results),
                "snippet_length": len(search_content),
                "retailer_content_length": len(retailer_content),
                "total_content_length": len(combined_content),
            })

            # Parse with AI
            prompt = self.WEB_SEARCH_PARSE_PROMPT.format(
                manufacturer=manufacturer or "Unknown",
                model_number=model_number,
                search_content=combined_content[:8000],  # Limit content size
            )

            response = await self.ai_provider.complete(prompt)

            if not response:
                debug_log("ENRICHMENT", "Empty AI response when parsing search results", level="WARNING")
                return None

            # Parse the AI response
            result = self._parse_ai_response(response, manufacturer, model_number, product_name)

            if result.enriched:
                # Mark source as web search
                result = EnrichmentResult(
                    enriched=result.enriched,
                    source=f"web_search:{self._search_provider.provider_name.lower()}",
                    name=result.name,
                    description=result.description,
                    features=result.features,
                    msrp=result.msrp,
                    release_year=result.release_year,
                    category=result.category,
                    additional_specs=result.additional_specs,
                    confidence=min(result.confidence + 0.1, 1.0),  # Boost confidence for web search
                )
                logger.info(f"Web search enrichment: name='{result.name}', features={len(result.features)}, "
                           f"msrp={result.msrp}, year={result.release_year}, category='{result.category}'")
            else:
                logger.info("Web search enrichment: no useful data extracted")

            return result

        except Exception as e:
            logger.error(f"Web search enrichment failed: {e}")
            debug_log("ENRICHMENT", f"Web search enrichment failed: {e}", level="ERROR")
            return None

    async def _ai_enrich(
        self,
        manufacturer: str,
        model_number: str,
        product_name: str,
    ) -> EnrichmentResult:
        """Use AI provider to enrich product data."""
        if not self.ai_provider:
            return EnrichmentResult.empty(product_name)

        try:
            # Build prompt
            hint = f"Hint: {product_name}" if product_name else ""
            prompt = self.ENRICHMENT_PROMPT.format(
                manufacturer=manufacturer or "Unknown",
                model_number=model_number,
                hint=hint,
            )

            debug_log("ENRICHMENT", "Calling AI provider", {
                "provider": type(self.ai_provider).__name__,
                "prompt_length": len(prompt),
            })

            # Call AI provider
            logger.info(f"Calling AI provider: {type(self.ai_provider).__name__}")
            response = await self.ai_provider.complete(prompt)

            if not response:
                logger.warning("Empty response from AI provider")
                debug_log("ENRICHMENT", "Empty response from AI provider", level="WARNING")
                return EnrichmentResult.empty(product_name)

            logger.info(f"AI response received: {len(response)} chars")
            logger.debug(f"AI raw response: {response[:500]}")
            debug_log("ENRICHMENT", "AI response received", {
                "response_length": len(response),
                "response_preview": response[:200] if len(response) > 200 else response,
            })

            # Parse JSON response
            result = self._parse_ai_response(
                response, manufacturer, model_number, product_name
            )

            # Log what was found
            if result.enriched:
                logger.info(f"Enrichment result: name='{result.name}', features={len(result.features)}, "
                           f"msrp={result.msrp}, year={result.release_year}, category='{result.category}'")
            else:
                logger.info(f"Enrichment returned no data for {manufacturer} {model_number}")

            return result

        except Exception as e:
            logger.exception(f"AI enrichment failed: {e}")
            debug_log("ENRICHMENT", f"AI enrichment failed: {e}", level="ERROR")
            return EnrichmentResult.empty(product_name)

    def _parse_ai_response(
        self,
        response: str,
        manufacturer: str,
        model_number: str,
        product_name: str,
    ) -> EnrichmentResult:
        """Parse AI response to EnrichmentResult."""
        try:
            # Clean response - extract JSON if wrapped in markdown
            response = response.strip()
            if response.startswith("```"):
                # Remove markdown code blocks
                lines = response.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```"):
                        in_block = not in_block
                        continue
                    if in_block or not line.startswith("```"):
                        json_lines.append(line)
                response = "\n".join(json_lines)

            data = json.loads(response)

            # Check if AI recognized the product
            if data.get("enriched") is False or not data.get("name"):
                logger.debug(f"AI did not recognize product: {manufacturer} {model_number}")
                return EnrichmentResult.empty(product_name)

            # Extract and validate fields
            name = data.get("name", "").strip()
            description = data.get("description", "").strip()
            features = data.get("features", [])
            msrp = data.get("msrp")
            release_year = data.get("release_year")
            category = data.get("category", "")

            # Validate features is a list of strings
            if not isinstance(features, list):
                features = []
            features = [str(f) for f in features if f][:8]

            # Validate msrp
            if msrp is not None:
                try:
                    msrp = float(msrp)
                    if msrp <= 0 or msrp > 100000:
                        msrp = None
                except (ValueError, TypeError):
                    msrp = None

            # Validate release_year
            if release_year is not None:
                try:
                    release_year = int(release_year)
                    if release_year < 2000 or release_year > 2030:
                        release_year = None
                except (ValueError, TypeError):
                    release_year = None

            # Auto-categorize if not provided
            if not category:
                category = EnrichmentParser.categorize_product(
                    manufacturer, model_number, name
                )

            # Calculate confidence
            confidence = 0.5  # Base confidence for AI response
            if features:
                confidence += 0.15
            if msrp:
                confidence += 0.15
            if release_year:
                confidence += 0.1
            if description:
                confidence += 0.1

            return EnrichmentResult(
                enriched=True,
                source="ai_knowledge",
                name=name or f"{manufacturer} {model_number}",
                description=description,
                features=features,
                msrp=msrp,
                release_year=release_year,
                category=category,
                additional_specs={},
                confidence=min(confidence, 1.0),
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")
            debug_log("ENRICHMENT", f"JSON parse error: {e}", {
                "response_preview": response[:500] if response else "",
            }, level="WARNING")
            return EnrichmentResult.empty(product_name)
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            debug_log("ENRICHMENT", f"Error parsing AI response: {e}", level="ERROR")
            return EnrichmentResult.empty(product_name)

    def format_description(self, result: EnrichmentResult) -> str:
        """Format enrichment data for Homebox description field."""
        parts = []

        # Main description
        if result.description:
            parts.append(result.description)

        # Features as bullet list
        if result.features:
            parts.append("\nFeatures:")
            for feature in result.features:
                parts.append(f"  - {feature}")

        # MSRP note
        if result.msrp:
            parts.append(f"\nOriginal MSRP: ${result.msrp:.2f}")

        # Release year
        if result.release_year:
            parts.append(f"Released: {result.release_year}")

        return "\n".join(parts)

    def clear_cache(self) -> int:
        """Clear the enrichment cache. Returns count of cleared entries."""
        return self.cache.clear()
