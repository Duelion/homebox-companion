"""
Enrichment Service - AI-powered product specification lookup.

This service enhances AI-extracted product data with detailed specifications
using the SAME AI provider already configured for item detection. No additional
API keys or external services are required.

The AI uses its training knowledge to elaborate on products given a
manufacturer and model number, providing features, typical MSRP, release
year, and other specifications.

Privacy considerations:
- Disabled by default (opt-in)
- Only manufacturer and model number are sent to the AI
- Serial numbers are NEVER sent externally
- Results are cached locally to minimize API calls
- Uses existing AI provider - no new accounts needed
"""

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from homebox_companion.providers.base import BaseProvider

logger = logging.getLogger(__name__)


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
    Service to enrich product data using the existing AI provider.

    This uses the SAME AI provider already configured for item detection,
    so no additional API keys or external services are required.
    The AI uses its training knowledge to elaborate on products.
    """

    # Prompt for AI enrichment
    ENRICHMENT_PROMPT = """You are a product specification expert. Given a manufacturer and model number, provide detailed product information from your knowledge.

Respond in JSON format with these fields:
{
  "name": "Full official product name",
  "description": "2-3 sentence product description",
  "features": ["Feature 1", "Feature 2", ...],
  "msrp": 999.99,
  "release_year": 2023,
  "category": "Product category"
}

Rules:
- Only include information you are confident about
- Set msrp to null if unknown
- Set release_year to null if unknown
- Features should be specific specs (e.g., "4K resolution", "20W speakers")
- Keep features list to 5-8 items maximum
- If you don't recognize this product, return {"name": "", "enriched": false}

Product to look up:
Manufacturer: {manufacturer}
Model: {model_number}
{hint}

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

    def set_provider(self, provider: "BaseProvider") -> None:
        """Set or update the AI provider."""
        self.ai_provider = provider

    async def enrich(
        self,
        manufacturer: str,
        model_number: str,
        product_name: str = "",
    ) -> EnrichmentResult:
        """
        Enrich product data with detailed specifications.

        Args:
            manufacturer: Product manufacturer
            model_number: Model/part number
            product_name: Optional product name hint

        Returns:
            EnrichmentResult with detailed specs
        """
        # Must have model number to enrich
        if not model_number or not model_number.strip():
            logger.debug("No model number provided, skipping enrichment")
            return EnrichmentResult.empty(product_name)

        # Must have AI provider
        if not self.ai_provider:
            logger.warning("No AI provider configured for enrichment")
            return EnrichmentResult.empty(product_name)

        model_number = model_number.strip()
        manufacturer = (manufacturer or "").strip()

        # Check cache first
        cached = self.cache.get(manufacturer, model_number)
        if cached is not None:
            return cached

        # Perform AI lookup
        logger.info(f"Enriching specs for {manufacturer} {model_number}")
        result = await self._ai_enrich(manufacturer, model_number, product_name)

        # Cache result (even if not enriched, to avoid repeated failed lookups)
        self.cache.set(manufacturer, model_number, result)

        return result

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

            # Call AI provider
            response = await self.ai_provider.complete(prompt)

            if not response:
                logger.warning("Empty response from AI provider")
                return EnrichmentResult.empty(product_name)

            # Parse JSON response
            return self._parse_ai_response(
                response, manufacturer, model_number, product_name
            )

        except Exception as e:
            logger.error(f"AI enrichment failed: {e}")
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
            return EnrichmentResult.empty(product_name)
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
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
