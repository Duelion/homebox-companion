"""FastAPI backend for the Homebox mobile web app."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from homebox import (
    DEMO_BASE_URL,
    AsyncHomeboxClient,
    DetectedItem,
    detect_items_from_bytes,
)

# Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


# Shared async client for connection pooling
_homebox_client: AsyncHomeboxClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage shared resources across the app lifecycle."""
    global _homebox_client
    _homebox_client = AsyncHomeboxClient(base_url=DEMO_BASE_URL)
    yield
    if _homebox_client:
        await _homebox_client.aclose()


app = FastAPI(
    title="Homebox Mobile API",
    description="Backend API for the Homebox mobile web app",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class LoginRequest(BaseModel):
    """Login credentials."""

    username: str = "demo@example.com"
    password: str = "demo"


class LoginResponse(BaseModel):
    """Login response with token."""

    token: str
    message: str = "Login successful"


class ItemInput(BaseModel):
    """Item data for creation."""

    name: str
    quantity: int = 1
    description: str | None = None
    location_id: str | None = None
    label_ids: list[str] | None = None


class BatchCreateRequest(BaseModel):
    """Batch item creation request."""

    items: list[ItemInput]
    location_id: str | None = None


class DetectedItemResponse(BaseModel):
    """Detected item from image analysis."""

    name: str
    quantity: int
    description: str | None = None
    label_ids: list[str] | None = None


class DetectionResponse(BaseModel):
    """Response from image detection."""

    items: list[DetectedItemResponse]
    message: str = "Detection complete"


def get_token(authorization: str | None) -> str:
    """Extract bearer token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    return authorization[7:]


def get_client() -> AsyncHomeboxClient:
    """Get the shared Homebox client."""
    if _homebox_client is None:
        raise HTTPException(status_code=500, detail="Client not initialized")
    return _homebox_client


# API Endpoints
@app.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Authenticate with Homebox and return bearer token."""
    client = get_client()
    try:
        token = await client.login(request.username, request.password)
        return LoginResponse(token=token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@app.get("/api/locations")
async def get_locations(
    authorization: Annotated[str | None, Header()] = None,
) -> list[dict[str, Any]]:
    """Fetch all available locations."""
    token = get_token(authorization)
    client = get_client()
    try:
        return await client.list_locations(token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/labels")
async def get_labels(
    authorization: Annotated[str | None, Header()] = None,
) -> list[dict[str, Any]]:
    """Fetch all available labels."""
    token = get_token(authorization)
    client = get_client()
    try:
        return await client.list_labels(token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/detect", response_model=DetectionResponse)
async def detect_items(
    image: Annotated[UploadFile, File(description="Image file to analyze")],
    authorization: Annotated[str | None, Header()] = None,
) -> DetectionResponse:
    """Analyze an uploaded image and detect items using OpenAI vision."""
    # Validate auth (even though detection doesn't require it, we want logged-in users)
    get_token(authorization)

    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY not configured",
        )

    # Read image bytes
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    # Determine MIME type
    content_type = image.content_type or "image/jpeg"

    # Fetch labels for context
    client = get_client()
    token = get_token(authorization)
    try:
        raw_labels = await client.list_labels(token)
        labels = [
            {"id": str(label.get("id", "")), "name": str(label.get("name", ""))}
            for label in raw_labels
            if label.get("id") and label.get("name")
        ]
    except Exception:
        labels = []

    # Detect items
    try:
        detected = detect_items_from_bytes(
            image_bytes=image_bytes,
            api_key=OPENAI_API_KEY,
            mime_type=content_type,
            model=OPENAI_MODEL,
            labels=labels,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {e}") from e

    return DetectionResponse(
        items=[
            DetectedItemResponse(
                name=item.name,
                quantity=item.quantity,
                description=item.description,
                label_ids=item.label_ids,
            )
            for item in detected
        ]
    )


@app.post("/api/items")
async def create_items(
    request: BatchCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    """Create multiple items in Homebox."""
    token = get_token(authorization)
    client = get_client()

    created: list[dict[str, Any]] = []
    errors: list[str] = []

    for item_input in request.items:
        # Use request-level location_id if item doesn't have one
        location_id = item_input.location_id or request.location_id

        detected_item = DetectedItem(
            name=item_input.name,
            quantity=item_input.quantity,
            description=item_input.description,
            location_id=location_id,
            label_ids=item_input.label_ids,
        )

        try:
            result = await client.create_item(token, detected_item)
            created.append(result)
        except Exception as e:
            errors.append(f"Failed to create '{item_input.name}': {e}")

    return JSONResponse(
        content={
            "created": created,
            "errors": errors,
            "message": (
                f"Created {len(created)} items"
                + (f", {len(errors)} failed" if errors else "")
            ),
        },
        status_code=200 if not errors else 207,  # 207 Multi-Status if partial success
    )


# Serve static frontend files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    """Serve the main HTML page."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

