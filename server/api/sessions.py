"""Session management API endpoints for crash recovery.

Provides endpoints for:
- List recoverable sessions
- Get session details
- Recover a session
- Delete/abandon a session
- Create new session
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from homebox_companion.services.state_manager import StateManager, ImageState

router = APIRouter(prefix="/sessions")

# Global state manager instance
_state_manager: StateManager | None = None


def get_state_manager() -> StateManager:
    """Get or create the state manager singleton."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


# =============================================================================
# Request/Response Models
# =============================================================================


class SessionCreateRequest(BaseModel):
    """Request to create a new session."""

    homebox_url: str = Field(..., description="Homebox server URL")
    location_id: str | None = Field(None, description="Selected location ID")
    location_name: str | None = Field(None, description="Selected location name")


class SessionCreateResponse(BaseModel):
    """Response from session creation."""

    session_id: str
    created_at: str


class ImageAddRequest(BaseModel):
    """Request to add an image to a session."""

    image_path: str = Field(..., description="Path to the image file")
    original_filename: str | None = Field(None, description="Original filename")


class ImageAddResponse(BaseModel):
    """Response from adding an image."""

    image_id: str
    status: str


class ProcessingStartRequest(BaseModel):
    """Request to start processing an image."""

    image_id: str = Field(..., description="Image ID to process")


class ProcessingCompleteRequest(BaseModel):
    """Request to mark processing complete."""

    image_id: str = Field(..., description="Image ID")
    result: dict[str, Any] = Field(..., description="Extraction result")


class ProcessingFailRequest(BaseModel):
    """Request to mark processing failed."""

    image_id: str = Field(..., description="Image ID")
    error: str = Field(..., description="Error message")


class SessionSummary(BaseModel):
    """Summary of a session for listing."""

    session_id: str
    status: str
    created_at: str
    location_name: str | None
    image_count: int
    pending_count: int
    failed_count: int
    completed_count: int


class SessionDetail(BaseModel):
    """Detailed session information."""

    session_id: str
    status: str
    created_at: str
    homebox_url: str
    location_id: str | None
    location_name: str | None
    images: list[dict[str, Any]]
    can_recover: bool


class RecoveryResponse(BaseModel):
    """Response from session recovery."""

    session_id: str
    recovered_images: list[dict[str, Any]]
    failed_images: list[dict[str, Any]]
    pending_images: list[dict[str, Any]]


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/recoverable", response_model=list[SessionSummary])
async def list_recoverable_sessions() -> list[SessionSummary]:
    """List all sessions that can be recovered.

    Returns sessions with pending or failed images that haven't been completed.
    """
    manager = get_state_manager()
    sessions = await manager.list_sessions()

    summaries = []
    for session in sessions:
        # Only include sessions that have recoverable state
        if session.get("can_recover", False) or session.get("pending_count", 0) > 0:
            summaries.append(
                SessionSummary(
                    session_id=session["session_id"],
                    status=session["status"],
                    created_at=session["created_at"],
                    location_name=session.get("location_name"),
                    image_count=session.get("image_count", 0),
                    pending_count=session.get("pending_count", 0),
                    failed_count=session.get("failed_count", 0),
                    completed_count=session.get("completed_count", 0),
                )
            )

    return summaries


@router.get("/all", response_model=list[SessionSummary])
async def list_all_sessions() -> list[SessionSummary]:
    """List all sessions regardless of status."""
    manager = get_state_manager()
    sessions = await manager.list_sessions()

    return [
        SessionSummary(
            session_id=s["session_id"],
            status=s["status"],
            created_at=s["created_at"],
            location_name=s.get("location_name"),
            image_count=s.get("image_count", 0),
            pending_count=s.get("pending_count", 0),
            failed_count=s.get("failed_count", 0),
            completed_count=s.get("completed_count", 0),
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str) -> SessionDetail:
    """Get detailed information about a specific session."""
    manager = get_state_manager()

    # Get session metadata
    meta = await manager.get_session(session_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all images for this session
    images = await manager.get_session_images(session_id)

    # Determine if session can be recovered
    pending_count = sum(1 for img in images if img.get("status") == "pending")
    failed_count = sum(1 for img in images if img.get("status") == "failed")
    can_recover = pending_count > 0 or failed_count > 0

    return SessionDetail(
        session_id=session_id,
        status=meta.get("status", "unknown"),
        created_at=meta.get("created_at", ""),
        homebox_url=meta.get("homebox_url", ""),
        location_id=meta.get("location_id"),
        location_name=meta.get("location_name"),
        images=images,
        can_recover=can_recover,
    )


@router.post("", response_model=SessionCreateResponse)
async def create_session(request: SessionCreateRequest) -> SessionCreateResponse:
    """Create a new session for tracking image processing."""
    manager = get_state_manager()

    session_id = manager.create_session(
        homebox_url=request.homebox_url,
        location_id=request.location_id,
        location_name=request.location_name,
    )

    # Get the created session to return timestamp
    meta = await manager.get_session(session_id)

    return SessionCreateResponse(
        session_id=session_id,
        created_at=meta.get("created_at", "") if meta else "",
    )


@router.post("/{session_id}/images", response_model=ImageAddResponse)
async def add_image(session_id: str, request: ImageAddRequest) -> ImageAddResponse:
    """Add an image to a session."""
    manager = get_state_manager()

    # Verify session exists
    meta = await manager.get_session(session_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Session not found")

    from pathlib import Path

    image_id = await manager.add_image(
        session_id=session_id,
        image_path=Path(request.image_path),
        original_filename=request.original_filename,
    )

    return ImageAddResponse(image_id=image_id, status="pending")


@router.post("/{session_id}/process/start")
async def start_processing(
    session_id: str, request: ProcessingStartRequest
) -> dict[str, Any]:
    """Mark an image as being processed."""
    manager = get_state_manager()

    result = await manager.start_processing(session_id, request.image_id)
    if not result:
        raise HTTPException(status_code=404, detail="Image not found")

    return {"status": "processing", "image_id": request.image_id}


@router.post("/{session_id}/process/complete")
async def complete_processing(
    session_id: str, request: ProcessingCompleteRequest
) -> dict[str, Any]:
    """Mark image processing as complete with results."""
    manager = get_state_manager()

    result = await manager.complete_processing(
        session_id, request.image_id, request.result
    )

    return {
        "status": "completed",
        "image_id": request.image_id,
        "has_result": result is not None,
    }


@router.post("/{session_id}/process/fail")
async def fail_processing(
    session_id: str, request: ProcessingFailRequest
) -> dict[str, Any]:
    """Mark image processing as failed."""
    manager = get_state_manager()

    result = await manager.fail_processing(session_id, request.image_id, request.error)

    return {
        "status": "failed",
        "image_id": request.image_id,
        "attempts": result.attempts if result else 0,
        "can_retry": result.attempts < 3 if result else False,
    }


@router.post("/{session_id}/recover", response_model=RecoveryResponse)
async def recover_session(session_id: str) -> RecoveryResponse:
    """Recover a session's state for resuming work.

    Returns all images grouped by status for the frontend to resume.
    """
    manager = get_state_manager()

    recovery_data = await manager.recover_session(session_id)

    if not recovery_data:
        raise HTTPException(status_code=404, detail="Session not found or not recoverable")

    return RecoveryResponse(
        session_id=session_id,
        recovered_images=recovery_data.get("completed", []),
        failed_images=recovery_data.get("failed", []),
        pending_images=recovery_data.get("pending", []),
    )


@router.post("/{session_id}/complete")
async def complete_session(session_id: str) -> dict[str, str]:
    """Mark a session as fully completed."""
    manager = get_state_manager()

    success = await manager.complete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"status": "completed", "session_id": session_id}


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    """Delete/abandon a session and its state files."""
    manager = get_state_manager()

    success = await manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"status": "deleted", "session_id": session_id}


@router.get("/check/active")
async def check_active_session() -> dict[str, Any]:
    """Check if there's an active recoverable session.

    This is a lightweight endpoint for the frontend to check on page load.
    """
    manager = get_state_manager()
    sessions = await manager.list_sessions()

    # Find the most recent recoverable session
    recoverable = [
        s for s in sessions
        if s.get("can_recover", False) or s.get("pending_count", 0) > 0
    ]

    if not recoverable:
        return {"has_recoverable": False, "session": None}

    # Return the most recent one
    most_recent = max(recoverable, key=lambda s: s.get("created_at", ""))

    return {
        "has_recoverable": True,
        "session": SessionSummary(
            session_id=most_recent["session_id"],
            status=most_recent["status"],
            created_at=most_recent["created_at"],
            location_name=most_recent.get("location_name"),
            image_count=most_recent.get("image_count", 0),
            pending_count=most_recent.get("pending_count", 0),
            failed_count=most_recent.get("failed_count", 0),
            completed_count=most_recent.get("completed_count", 0),
        ),
    }
