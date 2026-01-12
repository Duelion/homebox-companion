"""CSV-backed state manager for crash-proof session management.

This module provides persistent state management for capture sessions,
ensuring no work is lost due to crashes, timeouts, or restarts.

Design principles:
- Every state change is immediately persisted to disk
- CSV format for human readability and easy recovery
- File locking prevents corruption from concurrent access
- Automatic recovery moves stuck 'processing' items back to 'pending'

Usage:
    state_manager = StateManager(Path("/data"))
    session_id = state_manager.create_session("http://homebox:7745")

    # Add images
    image_id = await state_manager.add_image(session_id, image_path, "photo.jpg")

    # Process images
    state = await state_manager.start_processing(session_id, image_id)
    # ... do AI processing ...
    await state_manager.complete_processing(session_id, image_id, result)

    # Recovery after crash
    recovery_data = await state_manager.recover_session(session_id)
"""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from filelock import FileLock
from loguru import logger


@dataclass
class ImageState:
    """State of a single image in the processing pipeline.

    This is stored as a row in the manifest CSV file. All fields
    are strings or primitives for CSV compatibility.
    """

    image_id: str
    filename: str
    original_name: str
    status: str  # pending, processing, completed, failed, pushed
    attempts: int = 0
    last_attempt: str = ""
    created_at: str = ""
    name: str = ""
    manufacturer: str = ""
    model_number: str = ""
    serial_number: str = ""
    quantity: int = 1
    confidence: float = 0.0
    data_json: str = "{}"
    error: str = ""
    homebox_id: str = ""


class StateManager:
    """CSV-backed state manager for crash-proof session management.

    Provides persistent state for capture sessions with automatic
    recovery from crashes and interruptions.

    Attributes:
        data_dir: Root directory for all data storage
        sessions_dir: Directory containing session subdirectories
    """

    CSV_FIELDS = [
        "image_id",
        "filename",
        "original_name",
        "status",
        "attempts",
        "last_attempt",
        "created_at",
        "name",
        "manufacturer",
        "model_number",
        "serial_number",
        "quantity",
        "confidence",
        "data_json",
        "error",
        "homebox_id",
    ]

    def __init__(self, data_dir: Path, lock_timeout: int = 10):
        """Initialize state manager.

        Args:
            data_dir: Root directory for data storage
            lock_timeout: Timeout in seconds for acquiring file lock
        """
        self.data_dir = Path(data_dir)
        self.sessions_dir = self.data_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._lock = FileLock(self.data_dir / ".state.lock", timeout=lock_timeout)
        logger.debug(f"StateManager initialized with data_dir={data_dir}")

    # =========================================================================
    # Session Management
    # =========================================================================

    def create_session(
        self,
        homebox_url: str,
        location_id: str | None = None,
        location_name: str | None = None,
    ) -> str:
        """Create a new capture session.

        Args:
            homebox_url: URL of the Homebox instance
            location_id: Optional target location ID
            location_name: Optional target location name

        Returns:
            Session ID (e.g., "batch_20250105_143022")
        """
        # Include microseconds for uniqueness when creating sessions rapidly
        session_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        session_dir = self.sessions_dir / session_id

        with self._lock:
            # Create directory structure
            (session_dir / "pending").mkdir(parents=True)
            (session_dir / "processing").mkdir()
            (session_dir / "completed").mkdir()
            (session_dir / "failed").mkdir()

            # Create empty manifest with headers
            manifest_path = session_dir / "manifest.csv"
            with open(manifest_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_FIELDS)
                writer.writeheader()

            # Create session metadata
            meta = {
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "status": "created",
                "homebox": {
                    "url": homebox_url,
                    "location_id": location_id,
                    "location_name": location_name,
                },
                "settings": {
                    "ai_provider": "litellm",
                    "ai_model": "",
                    "enrichment_enabled": False,
                    "attach_photos": True,
                },
                "stats": {
                    "total": 0,
                    "pending": 0,
                    "processing": 0,
                    "completed": 0,
                    "failed": 0,
                    "pushed": 0,
                },
            }
            (session_dir / "session_meta.json").write_text(
                json.dumps(meta, indent=2), encoding="utf-8"
            )

            # Set as active session
            self._set_active_session(session_id)

        logger.info(f"Created session {session_id}")
        return session_id

    def get_active_session(self) -> str | None:
        """Get the current active session ID.

        Returns:
            Session ID if an active session exists, None otherwise
        """
        active_file = self.sessions_dir / "active_session.json"
        if active_file.exists():
            try:
                data = json.loads(active_file.read_text(encoding="utf-8"))
                session_id = data.get("session_id")
                # Verify session still exists
                if session_id and (self.sessions_dir / session_id).exists():
                    return session_id
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to read active session file: {e}")
        return None

    def get_session_meta(self, session_id: str) -> dict[str, Any]:
        """Get session metadata.

        Args:
            session_id: Session to get metadata for

        Returns:
            Session metadata dictionary
        """
        meta_path = self.sessions_dir / session_id / "session_meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Session {session_id} not found")
        return json.loads(meta_path.read_text(encoding="utf-8"))

    def get_session_stats(self, session_id: str) -> dict[str, int]:
        """Get current statistics for a session.

        Args:
            session_id: Session to get stats for

        Returns:
            Dictionary with counts for each status
        """
        states = self._read_manifest(session_id)
        stats = {
            "total": 0,
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "pushed": 0,
        }
        for state in states:
            stats["total"] += 1
            if state.status in stats:
                stats[state.status] += 1
        return stats

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions with their metadata.

        Returns:
            List of session metadata dictionaries
        """
        sessions = []
        for session_dir in self.sessions_dir.iterdir():
            if session_dir.is_dir() and session_dir.name.startswith("batch_"):
                meta_path = session_dir / "session_meta.json"
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        sessions.append(meta)
                    except (json.JSONDecodeError, OSError):
                        pass
        # Sort by created_at descending
        sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return sessions

    # =========================================================================
    # Image Management
    # =========================================================================

    async def add_image(
        self,
        session_id: str,
        image_path: Path,
        original_name: str,
    ) -> str:
        """Add an image to the session.

        Copies the image to the session's pending directory and creates
        a manifest entry.

        Args:
            session_id: Target session
            image_path: Path to uploaded image file
            original_name: Original filename from user

        Returns:
            Assigned image_id
        """
        with self._lock:
            session_dir = self.sessions_dir / session_id

            # Generate unique image ID using timestamp with microseconds
            timestamp = datetime.now().strftime("%H%M%S%f")[:9]
            image_id = f"img_{timestamp}"

            # Determine destination filename preserving extension
            suffix = Path(image_path).suffix.lower() or ".jpg"
            dest_filename = f"{image_id}{suffix}"

            # Copy image to pending directory
            dest_path = session_dir / "pending" / dest_filename
            shutil.copy(image_path, dest_path)

            # Create state record
            state = ImageState(
                image_id=image_id,
                filename=dest_filename,
                original_name=original_name,
                status="pending",
                created_at=datetime.now().isoformat(),
            )

            # Append to manifest
            self._append_to_manifest(session_id, state)

            # Update session metadata
            self._update_session_stats(session_id)

        logger.debug(f"Added image {image_id} to session {session_id}")
        return image_id

    async def start_processing(
        self, session_id: str, image_id: str
    ) -> ImageState | None:
        """Mark an image as processing and move to processing directory.

        Args:
            session_id: Session containing the image
            image_id: Image to start processing

        Returns:
            Updated ImageState, or None if image cannot be processed
        """
        with self._lock:
            state = self._get_image_state(session_id, image_id)
            if not state or state.status not in ("pending",):
                return None

            session_dir = self.sessions_dir / session_id

            # Move file to processing directory
            src = session_dir / "pending" / state.filename
            dst = session_dir / "processing" / state.filename

            if src.exists():
                shutil.move(str(src), str(dst))

            # Update state
            state.status = "processing"
            state.attempts += 1
            state.last_attempt = datetime.now().isoformat()
            self._update_manifest(session_id, state)
            self._update_session_stats(session_id)

        logger.debug(f"Started processing {image_id} (attempt {state.attempts})")
        return state

    async def complete_processing(
        self,
        session_id: str,
        image_id: str,
        result: dict[str, Any],
    ) -> ImageState:
        """Mark an image as successfully processed.

        Moves the image to the completed directory and saves the
        extraction result as JSON.

        Args:
            session_id: Session containing the image
            image_id: Image that was processed
            result: Extraction results from AI

        Returns:
            Updated ImageState
        """
        with self._lock:
            state = self._get_image_state(session_id, image_id)
            if not state:
                raise ValueError(f"Image {image_id} not found in session {session_id}")

            session_dir = self.sessions_dir / session_id

            # Move file to completed directory
            src = session_dir / "processing" / state.filename
            dst = session_dir / "completed" / state.filename

            if src.exists():
                shutil.move(str(src), str(dst))

            # Save full JSON data
            json_path = session_dir / "completed" / f"{image_id}.json"
            json_path.write_text(
                json.dumps(result, indent=2, default=str), encoding="utf-8"
            )

            # Update state with extracted fields
            fields = result.get("fields", {})
            confidence = result.get("confidence", {})

            state.status = "completed"
            state.name = fields.get("name", "")
            state.manufacturer = fields.get("manufacturer", "")
            state.model_number = fields.get("model_number", "")
            state.serial_number = fields.get("serial_number", "")
            state.quantity = fields.get("quantity", 1)
            state.confidence = confidence.get("overall", 0.0)
            state.data_json = json.dumps(result)
            state.error = ""

            self._update_manifest(session_id, state)
            self._update_session_stats(session_id)

        logger.info(f"Completed processing {image_id}: {state.name or 'unnamed'}")
        return state

    async def fail_processing(
        self,
        session_id: str,
        image_id: str,
        error: str,
        max_attempts: int = 3,
    ) -> ImageState:
        """Handle processing failure - retry or mark as failed.

        If the image has not exceeded max_attempts, it is moved back
        to pending for retry. Otherwise, it is moved to failed.

        Args:
            session_id: Session containing the image
            image_id: Image that failed
            error: Error message
            max_attempts: Maximum retry attempts before permanent failure

        Returns:
            Updated ImageState
        """
        with self._lock:
            state = self._get_image_state(session_id, image_id)
            if not state:
                raise ValueError(f"Image {image_id} not found in session {session_id}")

            session_dir = self.sessions_dir / session_id
            src = session_dir / "processing" / state.filename

            if state.attempts >= max_attempts:
                # Final failure - move to failed directory
                dst = session_dir / "failed" / state.filename
                state.status = "failed"

                # Save error log
                error_log = session_dir / "failed" / f"{image_id}_error.log"
                with open(error_log, "a", encoding="utf-8") as f:
                    f.write(
                        f"[{datetime.now().isoformat()}] "
                        f"Attempt {state.attempts}: {error}\n"
                    )
                logger.warning(
                    f"Image {image_id} failed after {state.attempts} attempts: {error}"
                )
            else:
                # Return to pending for retry
                dst = session_dir / "pending" / state.filename
                state.status = "pending"
                logger.debug(
                    f"Image {image_id} failed (attempt {state.attempts}), will retry"
                )

            if src.exists():
                shutil.move(str(src), str(dst))

            state.error = error
            self._update_manifest(session_id, state)
            self._update_session_stats(session_id)

        return state

    async def mark_pushed(
        self,
        session_id: str,
        image_id: str,
        homebox_id: str,
    ) -> ImageState:
        """Mark an image as successfully pushed to Homebox.

        Args:
            session_id: Session containing the image
            image_id: Image that was pushed
            homebox_id: ID assigned by Homebox

        Returns:
            Updated ImageState
        """
        with self._lock:
            state = self._get_image_state(session_id, image_id)
            if not state:
                raise ValueError(f"Image {image_id} not found in session {session_id}")

            state.status = "pushed"
            state.homebox_id = homebox_id
            self._update_manifest(session_id, state)
            self._update_session_stats(session_id)

        logger.info(f"Pushed {image_id} to Homebox as {homebox_id}")
        return state

    # =========================================================================
    # Recovery
    # =========================================================================

    async def recover_session(self, session_id: str) -> dict[str, Any]:
        """Recover from an interrupted session.

        Moves any 'processing' images back to 'pending' and returns
        the current session state for UI to resume.

        Args:
            session_id: Session to recover

        Returns:
            Dictionary with session state for UI
        """
        with self._lock:
            session_dir = self.sessions_dir / session_id

            # Move any files stuck in processing back to pending
            processing_dir = session_dir / "processing"
            pending_dir = session_dir / "pending"

            recovered_count = 0
            for f in processing_dir.iterdir():
                if f.is_file():
                    shutil.move(str(f), str(pending_dir / f.name))
                    recovered_count += 1

            # Update manifest - reset processing to pending
            states = self._read_manifest(session_id)
            for state in states:
                if state.status == "processing":
                    state.status = "pending"
            self._write_manifest(session_id, states)

            # Update stats
            self._update_session_stats(session_id)

        if recovered_count > 0:
            logger.info(
                f"Recovered session {session_id}: "
                f"moved {recovered_count} images from processing to pending"
            )

        # Return current state for UI
        return {
            "session_id": session_id,
            "stats": self.get_session_stats(session_id),
            "images": [asdict(s) for s in self._read_manifest(session_id)],
            "recovered_count": recovered_count,
        }

    def get_next_pending(self, session_id: str) -> ImageState | None:
        """Get the next pending image for processing.

        Args:
            session_id: Session to check

        Returns:
            Next pending ImageState, or None if none available
        """
        states = self._read_manifest(session_id)
        for state in states:
            if state.status == "pending":
                return state
        return None

    def get_all_images(self, session_id: str) -> list[ImageState]:
        """Get all images in a session.

        Args:
            session_id: Session to get images from

        Returns:
            List of ImageState for all images
        """
        return self._read_manifest(session_id)

    def get_completed_images(self, session_id: str) -> list[ImageState]:
        """Get all completed (ready for review) images.

        Args:
            session_id: Session to get images from

        Returns:
            List of ImageState for completed and pushed images
        """
        return [
            s
            for s in self._read_manifest(session_id)
            if s.status in ("completed", "pushed")
        ]

    def get_image_data(self, session_id: str, image_id: str) -> dict[str, Any] | None:
        """Get the full extraction data for a completed image.

        Args:
            session_id: Session containing the image
            image_id: Image to get data for

        Returns:
            Extraction result dictionary, or None if not available
        """
        json_path = self.sessions_dir / session_id / "completed" / f"{image_id}.json"
        if json_path.exists():
            try:
                return json.loads(json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return None

    def get_image_path(self, session_id: str, image_id: str) -> Path | None:
        """Get the current file path for an image.

        Args:
            session_id: Session containing the image
            image_id: Image to find

        Returns:
            Path to image file, or None if not found
        """
        state = self._get_image_state(session_id, image_id)
        if not state:
            return None

        session_dir = self.sessions_dir / session_id
        # Check each directory based on status
        for subdir in ("pending", "processing", "completed", "failed"):
            path = session_dir / subdir / state.filename
            if path.exists():
                return path
        return None

    # =========================================================================
    # Cleanup
    # =========================================================================

    def archive_session(self, session_id: str) -> None:
        """Move completed session to archive.

        Args:
            session_id: Session to archive
        """
        session_dir = self.sessions_dir / session_id
        archive_dir = self.data_dir / "archive"
        archive_dir.mkdir(exist_ok=True)

        with self._lock:
            if session_dir.exists():
                shutil.move(str(session_dir), str(archive_dir / session_id))
                logger.info(f"Archived session {session_id}")

            # Clear active session if this was it
            if self.get_active_session() == session_id:
                (self.sessions_dir / "active_session.json").unlink(missing_ok=True)

    def delete_session(self, session_id: str) -> None:
        """Permanently delete a session.

        Args:
            session_id: Session to delete
        """
        session_dir = self.sessions_dir / session_id

        with self._lock:
            if session_dir.exists():
                shutil.rmtree(session_dir)
                logger.info(f"Deleted session {session_id}")

            if self.get_active_session() == session_id:
                (self.sessions_dir / "active_session.json").unlink(missing_ok=True)

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _set_active_session(self, session_id: str) -> None:
        """Set the active session pointer."""
        active_file = self.sessions_dir / "active_session.json"
        active_file.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "activated_at": datetime.now().isoformat(),
                }
            ),
            encoding="utf-8",
        )

    def _read_manifest(self, session_id: str) -> list[ImageState]:
        """Read all image states from manifest CSV."""
        manifest_path = self.sessions_dir / session_id / "manifest.csv"
        states = []

        if not manifest_path.exists():
            return states

        with open(manifest_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert types from string
                row["attempts"] = int(row.get("attempts", 0) or 0)
                row["quantity"] = int(row.get("quantity", 1) or 1)
                row["confidence"] = float(row.get("confidence", 0.0) or 0.0)
                states.append(ImageState(**row))

        return states

    def _write_manifest(self, session_id: str, states: list[ImageState]) -> None:
        """Write all image states to manifest CSV."""
        manifest_path = self.sessions_dir / session_id / "manifest.csv"

        with open(manifest_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_FIELDS)
            writer.writeheader()
            for state in states:
                writer.writerow(asdict(state))

    def _append_to_manifest(self, session_id: str, state: ImageState) -> None:
        """Append a single image state to manifest CSV."""
        manifest_path = self.sessions_dir / session_id / "manifest.csv"

        with open(manifest_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_FIELDS)
            writer.writerow(asdict(state))

    def _update_manifest(self, session_id: str, updated_state: ImageState) -> None:
        """Update a single image state in manifest CSV."""
        states = self._read_manifest(session_id)
        for i, state in enumerate(states):
            if state.image_id == updated_state.image_id:
                states[i] = updated_state
                break
        self._write_manifest(session_id, states)

    def _get_image_state(self, session_id: str, image_id: str) -> ImageState | None:
        """Get state for a specific image."""
        states = self._read_manifest(session_id)
        for state in states:
            if state.image_id == image_id:
                return state
        return None

    def _update_session_stats(self, session_id: str) -> None:
        """Update session metadata with current stats."""
        stats = self.get_session_stats(session_id)
        meta_path = self.sessions_dir / session_id / "session_meta.json"

        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                meta["stats"] = stats
                meta["updated_at"] = datetime.now().isoformat()

                # Update status based on stats
                if stats["processing"] > 0:
                    meta["status"] = "processing"
                elif stats["pending"] > 0:
                    meta["status"] = "processing"
                elif stats["total"] == 0:
                    meta["status"] = "created"
                elif stats["pushed"] == stats["total"]:
                    meta["status"] = "pushed"
                elif stats["failed"] > 0 and stats["completed"] > 0:
                    meta["status"] = "mixed"
                elif stats["failed"] == stats["total"]:
                    meta["status"] = "failed"
                elif stats["completed"] > 0:
                    meta["status"] = "ready"

                meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to update session stats: {e}")
