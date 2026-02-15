"""QR code URL resolution endpoint.

Follows URL shortener redirects (e.g., bit.ly) to resolve the final destination URL.
This allows QR codes with shortened URLs to work with the location/asset ID parsers.

Security:
- Requires authentication (Bearer token) — not an open proxy
- HEAD-only requests — no response body is ever downloaded or executed
- 5-second timeout — prevents hanging on slow/malicious targets
- Max 10 redirects — prevents infinite redirect loops
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from server.dependencies import require_auth

router = APIRouter(prefix="/qr", dependencies=[Depends(require_auth)])

# Constants
RESOLVE_TIMEOUT_SECONDS = 5
MAX_REDIRECTS = 10


class ResolveRequest(BaseModel):
    """Request body for URL resolution."""

    url: str


class ResolveResponse(BaseModel):
    """Response body with the resolved URL."""

    resolved_url: str


@router.post("/resolve")
async def resolve_url(body: ResolveRequest) -> ResolveResponse:
    """Follow redirects on a URL and return the final destination.

    Used by the QR scanner to resolve shortened URLs (bit.ly, etc.)
    into full Homebox URLs that can be parsed for location/asset IDs.

    Uses HEAD requests only — no response body is downloaded.
    Falls back to a streamed GET if the server rejects HEAD (405).
    """
    url = body.url.strip()

    if not url:
        raise HTTPException(status_code=422, detail="URL is required")

    # Basic URL validation
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="URL must start with http:// or https://")

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            timeout=RESOLVE_TIMEOUT_SECONDS,
        ) as client:
            response = await client.head(url)

            # Some shorteners reject HEAD — fall back to GET without downloading body
            if response.status_code == 405:
                logger.debug(f"HEAD rejected (405) for {url}, falling back to streamed GET")
                async with client.stream("GET", url) as stream_response:
                    resolved = str(stream_response.url)
            else:
                resolved = str(response.url)

            logger.debug(f"QR URL resolved: {url} → {resolved}")
            return ResolveResponse(resolved_url=resolved)

    except httpx.TooManyRedirects:
        logger.warning(f"Too many redirects for URL: {url}")
        raise HTTPException(status_code=422, detail="Too many redirects") from None
    except httpx.TimeoutException:
        logger.warning(f"Timeout resolving URL: {url}")
        raise HTTPException(status_code=422, detail="URL resolution timed out") from None
    except httpx.RequestError as e:
        logger.warning(f"Failed to resolve URL {url}: {e}")
        raise HTTPException(status_code=422, detail="Could not resolve URL") from None
