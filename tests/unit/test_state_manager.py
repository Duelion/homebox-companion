"""Unit tests for StateManager crash recovery system.

Tests cover:
- Session creation and management
- Image state transitions
- Recovery from crashes (processing -> pending)
- File persistence (CSV manifest, JSON metadata)
- Concurrent access (file locking)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio

from homebox_companion.services.state_manager import ImageState, StateManager

pytestmark = [pytest.mark.unit]


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory for tests."""
    return tmp_path / "data"


@pytest.fixture
def state_manager(data_dir: Path) -> StateManager:
    """Create a StateManager instance for testing."""
    return StateManager(data_dir)


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """Create a sample image file for testing."""
    image_path = tmp_path / "test_image.jpg"
    # Create a minimal valid JPEG (smallest valid JPEG is ~125 bytes)
    # Using a simple placeholder that's valid enough for file operations
    image_path.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100)
    return image_path


class TestSessionCreation:
    """Tests for session creation and management."""

    def test_create_session_returns_id(self, state_manager: StateManager) -> None:
        """Session creation returns a valid session ID."""
        session_id = state_manager.create_session("http://homebox:7745")

        assert session_id.startswith("batch_")
        assert len(session_id) > 10

    def test_create_session_creates_directory_structure(
        self, state_manager: StateManager, data_dir: Path
    ) -> None:
        """Session creation creates expected directory structure."""
        session_id = state_manager.create_session("http://homebox:7745")
        session_dir = data_dir / "sessions" / session_id

        assert session_dir.exists()
        assert (session_dir / "pending").is_dir()
        assert (session_dir / "processing").is_dir()
        assert (session_dir / "completed").is_dir()
        assert (session_dir / "failed").is_dir()
        assert (session_dir / "manifest.csv").is_file()
        assert (session_dir / "session_meta.json").is_file()

    def test_create_session_initializes_manifest(
        self, state_manager: StateManager, data_dir: Path
    ) -> None:
        """Session creation initializes manifest CSV with headers."""
        session_id = state_manager.create_session("http://homebox:7745")
        manifest_path = data_dir / "sessions" / session_id / "manifest.csv"

        content = manifest_path.read_text()
        assert "image_id" in content
        assert "filename" in content
        assert "status" in content

    def test_create_session_stores_homebox_url(
        self, state_manager: StateManager, data_dir: Path
    ) -> None:
        """Session metadata stores Homebox URL."""
        homebox_url = "http://my-homebox:7745"
        session_id = state_manager.create_session(homebox_url)

        meta = state_manager.get_session_meta(session_id)
        assert meta["homebox"]["url"] == homebox_url

    def test_create_session_sets_active_session(
        self, state_manager: StateManager
    ) -> None:
        """Creating a session sets it as the active session."""
        session_id = state_manager.create_session("http://homebox:7745")

        assert state_manager.get_active_session() == session_id

    def test_get_active_session_returns_none_when_empty(
        self, state_manager: StateManager
    ) -> None:
        """get_active_session returns None when no session exists."""
        assert state_manager.get_active_session() is None


class TestImageManagement:
    """Tests for adding and managing images."""

    @pytest_asyncio.fixture
    async def session_with_image(
        self, state_manager: StateManager, sample_image: Path
    ) -> tuple[str, str]:
        """Create a session with one image added."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "original_photo.jpg"
        )
        return session_id, image_id

    @pytest.mark.asyncio
    async def test_add_image_returns_id(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """Adding an image returns a unique image ID."""
        session_id = state_manager.create_session("http://homebox:7745")

        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )

        assert image_id.startswith("img_")

    @pytest.mark.asyncio
    async def test_add_image_copies_to_pending(
        self, state_manager: StateManager, sample_image: Path, data_dir: Path
    ) -> None:
        """Adding an image copies it to the pending directory."""
        session_id = state_manager.create_session("http://homebox:7745")

        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )

        pending_dir = data_dir / "sessions" / session_id / "pending"
        pending_files = list(pending_dir.glob("*.jpg"))
        assert len(pending_files) == 1
        assert image_id in pending_files[0].name

    @pytest.mark.asyncio
    async def test_add_image_creates_manifest_entry(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """Adding an image creates a manifest entry with pending status."""
        session_id = state_manager.create_session("http://homebox:7745")

        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )

        images = state_manager.get_all_images(session_id)
        assert len(images) == 1
        assert images[0].image_id == image_id
        assert images[0].status == "pending"
        assert images[0].original_name == "photo.jpg"

    @pytest.mark.asyncio
    async def test_add_image_updates_stats(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """Adding an image updates session statistics."""
        session_id = state_manager.create_session("http://homebox:7745")

        await state_manager.add_image(session_id, sample_image, "photo.jpg")

        stats = state_manager.get_session_stats(session_id)
        assert stats["total"] == 1
        assert stats["pending"] == 1


class TestProcessingWorkflow:
    """Tests for the image processing workflow."""

    @pytest.mark.asyncio
    async def test_start_processing_moves_file(
        self, state_manager: StateManager, sample_image: Path, data_dir: Path
    ) -> None:
        """Starting processing moves file from pending to processing."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )

        await state_manager.start_processing(session_id, image_id)

        session_dir = data_dir / "sessions" / session_id
        assert len(list((session_dir / "pending").glob("*"))) == 0
        assert len(list((session_dir / "processing").glob("*.jpg"))) == 1

    @pytest.mark.asyncio
    async def test_start_processing_updates_status(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """Starting processing updates image status to processing."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )

        state = await state_manager.start_processing(session_id, image_id)

        assert state is not None
        assert state.status == "processing"
        assert state.attempts == 1

    @pytest.mark.asyncio
    async def test_start_processing_increments_attempts(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """Each processing attempt increments the attempts counter."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )

        # First attempt
        await state_manager.start_processing(session_id, image_id)
        await state_manager.fail_processing(session_id, image_id, "error 1")

        # Second attempt
        state = await state_manager.start_processing(session_id, image_id)
        assert state.attempts == 2

    @pytest.mark.asyncio
    async def test_complete_processing_moves_to_completed(
        self, state_manager: StateManager, sample_image: Path, data_dir: Path
    ) -> None:
        """Completing processing moves file to completed directory."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )
        await state_manager.start_processing(session_id, image_id)

        result = {
            "fields": {"name": "Test Item", "manufacturer": "Acme"},
            "confidence": {"overall": 0.95},
        }
        await state_manager.complete_processing(session_id, image_id, result)

        session_dir = data_dir / "sessions" / session_id
        assert len(list((session_dir / "processing").glob("*"))) == 0
        assert len(list((session_dir / "completed").glob("*.jpg"))) == 1
        assert (session_dir / "completed" / f"{image_id}.json").exists()

    @pytest.mark.asyncio
    async def test_complete_processing_stores_extracted_fields(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """Completing processing stores extracted fields in manifest."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )
        await state_manager.start_processing(session_id, image_id)

        result = {
            "fields": {
                "name": "Test Item",
                "manufacturer": "Acme",
                "model_number": "XYZ-123",
            },
            "confidence": {"overall": 0.95},
        }
        state = await state_manager.complete_processing(session_id, image_id, result)

        assert state.status == "completed"
        assert state.name == "Test Item"
        assert state.manufacturer == "Acme"
        assert state.model_number == "XYZ-123"
        assert state.confidence == 0.95


class TestFailureHandling:
    """Tests for failure handling and retries."""

    @pytest.mark.asyncio
    async def test_fail_processing_returns_to_pending(
        self, state_manager: StateManager, sample_image: Path, data_dir: Path
    ) -> None:
        """Failed processing (under max retries) returns to pending."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )
        await state_manager.start_processing(session_id, image_id)

        state = await state_manager.fail_processing(
            session_id, image_id, "AI timeout", max_attempts=3
        )

        assert state.status == "pending"
        session_dir = data_dir / "sessions" / session_id
        assert len(list((session_dir / "pending").glob("*.jpg"))) == 1

    @pytest.mark.asyncio
    async def test_fail_processing_moves_to_failed_after_max_attempts(
        self, state_manager: StateManager, sample_image: Path, data_dir: Path
    ) -> None:
        """Failed processing after max attempts moves to failed directory."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )

        # Simulate 3 failed attempts
        for i in range(3):
            await state_manager.start_processing(session_id, image_id)
            state = await state_manager.fail_processing(
                session_id, image_id, f"error {i+1}", max_attempts=3
            )

        assert state.status == "failed"
        session_dir = data_dir / "sessions" / session_id
        assert len(list((session_dir / "failed").glob("*.jpg"))) == 1
        assert (session_dir / "failed" / f"{image_id}_error.log").exists()

    @pytest.mark.asyncio
    async def test_fail_processing_logs_errors(
        self, state_manager: StateManager, sample_image: Path, data_dir: Path
    ) -> None:
        """Failed processing logs final error message when max attempts reached."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )

        # Simulate failures until max attempts
        for i in range(3):
            await state_manager.start_processing(session_id, image_id)
            await state_manager.fail_processing(
                session_id, image_id, f"Error message {i+1}", max_attempts=3
            )

        # Error log is only created when image reaches failed state
        error_log = (
            data_dir / "sessions" / session_id / "failed" / f"{image_id}_error.log"
        )
        content = error_log.read_text()
        # Only the final error is logged (when max attempts reached)
        assert "Error message 3" in content
        assert "Attempt 3" in content


class TestRecovery:
    """Tests for crash recovery functionality."""

    @pytest.mark.asyncio
    async def test_recover_session_moves_processing_to_pending(
        self, state_manager: StateManager, sample_image: Path, data_dir: Path
    ) -> None:
        """Recovery moves stuck 'processing' images back to 'pending'."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )
        await state_manager.start_processing(session_id, image_id)

        # Simulate crash - image stuck in processing
        session_dir = data_dir / "sessions" / session_id
        assert len(list((session_dir / "processing").glob("*.jpg"))) == 1

        # Recovery
        result = await state_manager.recover_session(session_id)

        # Verify file moved
        assert len(list((session_dir / "processing").glob("*"))) == 0
        assert len(list((session_dir / "pending").glob("*.jpg"))) == 1

        # Verify manifest updated
        images = state_manager.get_all_images(session_id)
        assert images[0].status == "pending"

        # Verify recovery result
        assert result["recovered_count"] == 1

    @pytest.mark.asyncio
    async def test_recover_session_preserves_completed(
        self, state_manager: StateManager, sample_image: Path, data_dir: Path
    ) -> None:
        """Recovery preserves completed items."""
        session_id = state_manager.create_session("http://homebox:7745")

        # Add and complete one image
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )
        await state_manager.start_processing(session_id, image_id)
        await state_manager.complete_processing(
            session_id,
            image_id,
            {"fields": {"name": "Item"}, "confidence": {"overall": 0.9}},
        )

        # Recovery should not affect completed items
        await state_manager.recover_session(session_id)

        images = state_manager.get_all_images(session_id)
        assert images[0].status == "completed"

    @pytest.mark.asyncio
    async def test_recover_session_returns_current_state(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """Recovery returns current session state for UI."""
        session_id = state_manager.create_session("http://homebox:7745")
        await state_manager.add_image(session_id, sample_image, "photo1.jpg")
        await state_manager.add_image(session_id, sample_image, "photo2.jpg")

        result = await state_manager.recover_session(session_id)

        assert result["session_id"] == session_id
        assert result["stats"]["total"] == 2
        assert len(result["images"]) == 2


class TestPushWorkflow:
    """Tests for pushing items to Homebox."""

    @pytest.mark.asyncio
    async def test_mark_pushed_updates_status(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """Marking as pushed updates status and stores Homebox ID."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )
        await state_manager.start_processing(session_id, image_id)
        await state_manager.complete_processing(
            session_id,
            image_id,
            {"fields": {"name": "Item"}, "confidence": {"overall": 0.9}},
        )

        homebox_id = "abc-123-def"
        state = await state_manager.mark_pushed(session_id, image_id, homebox_id)

        assert state.status == "pushed"
        assert state.homebox_id == homebox_id


class TestCleanup:
    """Tests for session cleanup operations."""

    def test_delete_session_removes_directory(
        self, state_manager: StateManager, data_dir: Path
    ) -> None:
        """Deleting a session removes its directory."""
        session_id = state_manager.create_session("http://homebox:7745")
        session_dir = data_dir / "sessions" / session_id
        assert session_dir.exists()

        state_manager.delete_session(session_id)

        assert not session_dir.exists()

    def test_delete_session_clears_active(
        self, state_manager: StateManager
    ) -> None:
        """Deleting the active session clears the active pointer."""
        session_id = state_manager.create_session("http://homebox:7745")
        assert state_manager.get_active_session() == session_id

        state_manager.delete_session(session_id)

        assert state_manager.get_active_session() is None

    def test_archive_session_moves_to_archive(
        self, state_manager: StateManager, data_dir: Path
    ) -> None:
        """Archiving a session moves it to the archive directory."""
        session_id = state_manager.create_session("http://homebox:7745")

        state_manager.archive_session(session_id)

        assert not (data_dir / "sessions" / session_id).exists()
        assert (data_dir / "archive" / session_id).exists()


class TestQueryMethods:
    """Tests for query methods."""

    @pytest.mark.asyncio
    async def test_get_next_pending_returns_first_pending(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """get_next_pending returns the first pending image."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id1 = await state_manager.add_image(
            session_id, sample_image, "photo1.jpg"
        )
        await state_manager.add_image(session_id, sample_image, "photo2.jpg")

        next_image = state_manager.get_next_pending(session_id)

        assert next_image is not None
        assert next_image.image_id == image_id1

    @pytest.mark.asyncio
    async def test_get_next_pending_returns_none_when_empty(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """get_next_pending returns None when no pending images."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )
        await state_manager.start_processing(session_id, image_id)
        await state_manager.complete_processing(
            session_id,
            image_id,
            {"fields": {"name": "Item"}, "confidence": {"overall": 0.9}},
        )

        next_image = state_manager.get_next_pending(session_id)

        assert next_image is None

    @pytest.mark.asyncio
    async def test_get_completed_images(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """get_completed_images returns only completed and pushed images."""
        session_id = state_manager.create_session("http://homebox:7745")

        # Add images in various states
        img1 = await state_manager.add_image(session_id, sample_image, "p1.jpg")
        img2 = await state_manager.add_image(session_id, sample_image, "p2.jpg")
        img3 = await state_manager.add_image(session_id, sample_image, "p3.jpg")

        # Complete first image
        await state_manager.start_processing(session_id, img1)
        await state_manager.complete_processing(
            session_id, img1, {"fields": {"name": "A"}, "confidence": {"overall": 0.9}}
        )

        # Push second image
        await state_manager.start_processing(session_id, img2)
        await state_manager.complete_processing(
            session_id, img2, {"fields": {"name": "B"}, "confidence": {"overall": 0.9}}
        )
        await state_manager.mark_pushed(session_id, img2, "homebox-123")

        # Leave third as pending

        completed = state_manager.get_completed_images(session_id)

        assert len(completed) == 2
        statuses = {img.status for img in completed}
        assert statuses == {"completed", "pushed"}

    def test_list_sessions(self, state_manager: StateManager) -> None:
        """list_sessions returns all sessions sorted by creation time."""
        # Create multiple sessions
        id1 = state_manager.create_session("http://homebox:7745")
        id2 = state_manager.create_session("http://homebox:7745")
        id3 = state_manager.create_session("http://homebox:7745")

        sessions = state_manager.list_sessions()

        assert len(sessions) == 3
        # Most recent first
        assert sessions[0]["session_id"] == id3
        assert sessions[2]["session_id"] == id1

    @pytest.mark.asyncio
    async def test_get_image_data(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """get_image_data returns full extraction data for completed image."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )
        await state_manager.start_processing(session_id, image_id)

        result = {
            "fields": {"name": "Test", "serial_number": "SN123"},
            "confidence": {"overall": 0.95},
            "extra_data": "preserved",
        }
        await state_manager.complete_processing(session_id, image_id, result)

        data = state_manager.get_image_data(session_id, image_id)

        assert data is not None
        assert data["fields"]["name"] == "Test"
        assert data["extra_data"] == "preserved"

    @pytest.mark.asyncio
    async def test_get_image_path(
        self, state_manager: StateManager, sample_image: Path
    ) -> None:
        """get_image_path returns the current path of an image."""
        session_id = state_manager.create_session("http://homebox:7745")
        image_id = await state_manager.add_image(
            session_id, sample_image, "photo.jpg"
        )

        # Pending state
        path = state_manager.get_image_path(session_id, image_id)
        assert path is not None
        assert "pending" in str(path)

        # Processing state
        await state_manager.start_processing(session_id, image_id)
        path = state_manager.get_image_path(session_id, image_id)
        assert "processing" in str(path)

        # Completed state
        await state_manager.complete_processing(
            session_id,
            image_id,
            {"fields": {"name": "X"}, "confidence": {"overall": 0.9}},
        )
        path = state_manager.get_image_path(session_id, image_id)
        assert "completed" in str(path)
