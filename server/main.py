"""FastAPI backend for the Homebox Vision Companion web app."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel

from homebox_vision import (
    AsyncHomeboxClient,
    DetectedItem,
    analyze_item_details_from_images,
    correct_item_with_openai,
    detect_items_from_bytes,
    encode_image_bytes_to_data_uri,
    merge_items_with_openai,
    settings,
)

# Configure loguru
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    level=settings.log_level,
    colorize=True,
)
logger.add(
    "logs/homebox_vision_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
)

logger.info("Starting Homebox Vision Companion API")
logger.info(f"Homebox API URL: {settings.api_url}")
logger.info(f"OpenAI Model: {settings.openai_model}")
if settings.is_demo_mode:
    logger.warning("Using demo server - set HOMEBOX_VISION_API_URL for your own instance")

# Validate settings on startup
for issue in settings.validate():
    logger.warning(issue)


# Shared async client for connection pooling
_homebox_client: AsyncHomeboxClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage shared resources across the app lifecycle."""
    global _homebox_client
    _homebox_client = AsyncHomeboxClient(base_url=settings.api_url)
    yield
    if _homebox_client:
        await _homebox_client.aclose()


app = FastAPI(
    title="Homebox Vision Companion",
    description="AI-powered item detection for Homebox inventory management",
    version="0.9.0",
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

    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response with token."""

    token: str
    message: str = "Login successful"


class ItemInput(BaseModel):
    """Item data for creation with all Homebox fields."""

    name: str
    quantity: int = 1
    description: str | None = None
    location_id: str | None = None
    label_ids: list[str] | None = None
    # Advanced fields
    serial_number: str | None = None
    model_number: str | None = None
    manufacturer: str | None = None
    purchase_price: float | None = None
    purchase_from: str | None = None
    notes: str | None = None
    insured: bool = False


class BatchCreateRequest(BaseModel):
    """Batch item creation request."""

    items: list[ItemInput]
    location_id: str | None = None


class AdvancedAnalysisRequest(BaseModel):
    """Request for advanced item analysis with multiple images."""

    item_name: str
    item_description: str | None = None


class AdvancedItemDetails(BaseModel):
    """Detailed item information from AI analysis."""

    name: str | None = None
    description: str | None = None
    serial_number: str | None = None
    model_number: str | None = None
    manufacturer: str | None = None
    purchase_price: float | None = None
    notes: str | None = None
    label_ids: list[str] | None = None


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
    logger.info(f"Login attempt for user: {request.username}")
    client = get_client()
    try:
        token = await client.login(request.username, request.password)
        logger.info(f"Login successful for user: {request.username}")
        return LoginResponse(token=token)
    except Exception as e:
        logger.warning(f"Login failed for user {request.username}: {e}")
        raise HTTPException(status_code=401, detail=str(e)) from e


@app.get("/api/locations")
async def get_locations(
    authorization: Annotated[str | None, Header()] = None,
    filter_children: bool | None = None,
) -> list[dict[str, Any]]:
    """Fetch all available locations.

    Args:
        filter_children: If true, returns only top-level locations (no children).
    """
    token = get_token(authorization)
    client = get_client()
    try:
        return await client.list_locations(token, filter_children=filter_children)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/locations/tree")
async def get_locations_tree(
    authorization: Annotated[str | None, Header()] = None,
) -> list[dict[str, Any]]:
    """Fetch top-level locations with children info for hierarchical navigation.

    Returns locations with their children embedded for building a tree UI.
    """
    token = get_token(authorization)
    client = get_client()
    try:
        # Get only top-level locations (those without parents)
        top_level = await client.list_locations(token, filter_children=True)

        # Fetch details for each to get children info
        enriched = []
        for loc in top_level:
            try:
                details = await client.get_location(token, loc["id"])
                enriched.append({
                    "id": details.get("id"),
                    "name": details.get("name"),
                    "description": details.get("description", ""),
                    "itemCount": loc.get("itemCount", 0),
                    "children": details.get("children", []),
                })
            except Exception:
                # If we can't get details, include basic info without children
                enriched.append({
                    "id": loc.get("id"),
                    "name": loc.get("name"),
                    "description": loc.get("description", ""),
                    "itemCount": loc.get("itemCount", 0),
                    "children": [],
                })

        return enriched
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/locations/{location_id}")
async def get_location(
    location_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Fetch a specific location by ID with its children."""
    token = get_token(authorization)
    client = get_client()
    try:
        return await client.get_location(token, location_id)
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
    logger.info(f"Detecting items from image: {image.filename}")

    # Validate auth (even though detection doesn't require it, we want logged-in users)
    get_token(authorization)

    if not settings.openai_api_key:
        logger.error("HOMEBOX_VISION_OPENAI_API_KEY not configured")
        raise HTTPException(
            status_code=500,
            detail="HOMEBOX_VISION_OPENAI_API_KEY not configured",
        )

    # Read image bytes
    image_bytes = await image.read()
    if not image_bytes:
        logger.warning("Empty image file received")
        raise HTTPException(status_code=400, detail="Empty image file")

    logger.debug(f"Image size: {len(image_bytes)} bytes")

    # Determine MIME type
    content_type = image.content_type or "image/jpeg"
    logger.debug(f"Content type: {content_type}")

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
        logger.debug(f"Loaded {len(labels)} labels for context")
    except Exception as e:
        logger.warning(f"Failed to load labels: {e}")
        labels = []

    # Detect items
    try:
        logger.info("Starting OpenAI vision detection...")
        detected = detect_items_from_bytes(
            image_bytes=image_bytes,
            api_key=settings.openai_api_key,
            mime_type=content_type,
            model=settings.openai_model,
            labels=labels,
        )
        logger.info(f"Detected {len(detected)} items")
        for item in detected:
            logger.debug(f"  - {item.name} (qty: {item.quantity}, labels: {item.label_ids})")
    except Exception as e:
        logger.error(f"Detection failed: {e}")
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
    logger.info(f"Creating {len(request.items)} items")
    logger.debug(f"Request location_id: {request.location_id}")

    token = get_token(authorization)
    client = get_client()

    created: list[dict[str, Any]] = []
    errors: list[str] = []

    for item_input in request.items:
        # Use request-level location_id if item doesn't have one
        location_id = item_input.location_id or request.location_id

        logger.debug(f"Creating item: {item_input.name}")
        logger.debug(f"  location_id: {location_id}")
        logger.debug(f"  label_ids: {item_input.label_ids}")

        detected_item = DetectedItem(
            name=item_input.name,
            quantity=item_input.quantity,
            description=item_input.description,
            location_id=location_id,
            label_ids=item_input.label_ids,
        )

        try:
            result = await client.create_item(token, detected_item)
            logger.info(f"Created item: {result.get('name')} (id: {result.get('id')})")
            created.append(result)
        except Exception as e:
            error_msg = f"Failed to create '{item_input.name}': {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    logger.info(f"Item creation complete: {len(created)} created, {len(errors)} failed")
    if errors:
        for err in errors:
            logger.warning(f"  Error: {err}")

    return JSONResponse(
        content={
            "created": created,
            "errors": errors,
            "message": (
                f"Created {len(created)} items" + (f", {len(errors)} failed" if errors else "")
            ),
        },
        status_code=200 if not errors else 207,  # 207 Multi-Status if partial success
    )


@app.post("/api/analyze-advanced")
async def analyze_item_advanced(
    images: Annotated[list[UploadFile], File(description="Images to analyze")],
    item_name: Annotated[str, Form()],
    item_description: Annotated[str | None, Form()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> AdvancedItemDetails:
    """Analyze multiple images to extract detailed item information."""
    logger.info(f"Advanced analysis for item: {item_name}")
    logger.debug(f"Description: {item_description}")
    logger.debug(f"Number of images: {len(images) if images else 0}")

    get_token(authorization)

    if not settings.openai_api_key:
        logger.error("HOMEBOX_VISION_OPENAI_API_KEY not configured")
        raise HTTPException(status_code=500, detail="HOMEBOX_VISION_OPENAI_API_KEY not configured")

    if not images:
        logger.warning("No images provided for analysis")
        raise HTTPException(status_code=400, detail="At least one image is required")

    # Convert images to data URIs
    image_data_uris = []
    for img in images:
        img_bytes = await img.read()
        if img_bytes:
            mime_type = img.content_type or "image/jpeg"
            data_uri = encode_image_bytes_to_data_uri(img_bytes, mime_type)
            image_data_uris.append(data_uri)

    if not image_data_uris:
        raise HTTPException(status_code=400, detail="No valid images provided")

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

    # Analyze images
    try:
        logger.info(f"Analyzing {len(image_data_uris)} images with OpenAI...")
        details = analyze_item_details_from_images(
            image_data_uris=image_data_uris,
            item_name=item_name,
            item_description=item_description,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            labels=labels,
        )
        logger.info("Analysis complete")
        logger.debug(f"Analysis result: {details}")
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}") from e

    result = AdvancedItemDetails(
        name=details.get("name"),
        description=details.get("description"),
        serial_number=details.get("serialNumber"),
        model_number=details.get("modelNumber"),
        manufacturer=details.get("manufacturer"),
        purchase_price=details.get("purchasePrice"),
        notes=details.get("notes"),
        label_ids=details.get("labelIds"),
    )
    logger.debug(f"Returning: {result}")
    return result


class MergeItemsRequest(BaseModel):
    """Request to merge multiple items into one."""

    items: list[dict]


class MergedItemResponse(BaseModel):
    """Response with merged item data."""

    name: str
    quantity: int
    description: str | None = None
    label_ids: list[str] | None = None


@app.post("/api/merge-items", response_model=MergedItemResponse)
async def merge_items(
    request: MergeItemsRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> MergedItemResponse:
    """Merge multiple items into a single consolidated item using AI."""
    logger.info(f"Merging {len(request.items)} items")
    for item in request.items:
        logger.debug(f"  - {item.get('name')}: {item.get('description', '')[:50]}")

    get_token(authorization)

    if not settings.openai_api_key:
        logger.error("HOMEBOX_VISION_OPENAI_API_KEY not configured")
        raise HTTPException(status_code=500, detail="HOMEBOX_VISION_OPENAI_API_KEY not configured")

    if len(request.items) < 2:
        raise HTTPException(status_code=400, detail="At least 2 items are required to merge")

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

    try:
        logger.info("Calling OpenAI for item merge...")
        merged = merge_items_with_openai(
            items=request.items,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            labels=labels,
        )
        logger.info(f"Merge complete: {merged.get('name')}")
    except Exception as e:
        logger.error(f"Merge failed: {e}")
        raise HTTPException(status_code=500, detail=f"Merge failed: {e}") from e

    return MergedItemResponse(
        name=merged.get("name", "Merged Item"),
        quantity=merged.get("quantity", sum(item.get("quantity", 1) for item in request.items)),
        description=merged.get("description"),
        label_ids=merged.get("labelIds"),
    )


class CorrectionRequest(BaseModel):
    """Request to correct an item based on user feedback."""

    current_item: dict
    correction_instructions: str


class CorrectedItemResponse(BaseModel):
    """A corrected item from AI analysis."""

    name: str
    quantity: int
    description: str | None = None
    label_ids: list[str] | None = None


class CorrectionResponse(BaseModel):
    """Response with corrected item(s)."""

    items: list[CorrectedItemResponse]
    message: str = "Correction complete"


@app.post("/api/correct-item", response_model=CorrectionResponse)
async def correct_item(
    image: Annotated[UploadFile, File(description="Original image of the item")],
    current_item: Annotated[str, Form(description="JSON string of current item")],
    correction_instructions: Annotated[str, Form(description="User's correction feedback")],
    authorization: Annotated[str | None, Header()] = None,
) -> CorrectionResponse:
    """Correct an item based on user feedback.

    This endpoint allows users to provide feedback about a detected item,
    such as "actually these are soldering tips, not screws" or
    "these are two separate items: wire solder and paste solder".

    The AI will re-analyze the image with the user's feedback and return
    either a single corrected item or multiple items if the user indicated
    they should be split.
    """
    logger.info("Item correction request received")
    logger.debug(f"Correction instructions: {correction_instructions}")

    get_token(authorization)

    if not settings.openai_api_key:
        logger.error("HOMEBOX_VISION_OPENAI_API_KEY not configured")
        raise HTTPException(
            status_code=500,
            detail="HOMEBOX_VISION_OPENAI_API_KEY not configured",
        )

    # Parse current item from JSON string
    try:
        import json
        current_item_dict = json.loads(current_item)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON for current_item: {e}")
        raise HTTPException(status_code=400, detail="Invalid current_item JSON") from e

    logger.debug(f"Current item: {current_item_dict}")

    # Read and encode image
    image_bytes = await image.read()
    if not image_bytes:
        logger.warning("Empty image file received")
        raise HTTPException(status_code=400, detail="Empty image file")

    content_type = image.content_type or "image/jpeg"
    image_data_uri = encode_image_bytes_to_data_uri(image_bytes, content_type)

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
        logger.debug(f"Loaded {len(labels)} labels for context")
    except Exception as e:
        logger.warning(f"Failed to load labels: {e}")
        labels = []

    # Call the correction function
    try:
        logger.info("Starting OpenAI item correction...")
        corrected_items = correct_item_with_openai(
            image_data_uri=image_data_uri,
            current_item=current_item_dict,
            correction_instructions=correction_instructions,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            labels=labels,
        )
        logger.info(f"Correction resulted in {len(corrected_items)} item(s)")
    except Exception as e:
        logger.error(f"Item correction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Correction failed: {e}") from e

    return CorrectionResponse(
        items=[
            CorrectedItemResponse(
                name=item.get("name", "Unknown"),
                quantity=item.get("quantity", 1),
                description=item.get("description"),
                label_ids=item.get("labelIds"),
            )
            for item in corrected_items
        ],
        message=f"Corrected to {len(corrected_items)} item(s)",
    )


@app.post("/api/items/{item_id}/attachments")
async def upload_item_attachment(
    item_id: str,
    file: Annotated[UploadFile, File(description="Image file to upload")],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Upload an attachment (image) to an existing item."""
    token = get_token(authorization)
    client = get_client()

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    filename = file.filename or "image.jpg"
    mime_type = file.content_type or "image/jpeg"

    try:
        result = await client.upload_attachment(
            token=token,
            item_id=item_id,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
            attachment_type="photo",
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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


def run():
    """Entry point for the homebox-vision CLI command."""
    import uvicorn

    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
    )


if __name__ == "__main__":
    run()
