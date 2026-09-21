"""Request limits stop uploads before buffering and clean up interrupted files."""

from __future__ import annotations

import tempfile
from typing import Annotated

import httpx
import pytest
from fastapi import FastAPI, File, Request, UploadFile
from pydantic import ValidationError

from homebox_companion.core.config import Settings
from server.app import create_app
from server.middleware import RequestBodyLimitMiddleware

pytestmark = pytest.mark.asyncio


def make_app(*, limit_mb: int = 1, api_key: bool = False) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        RequestBodyLimitMiddleware,
        settings=Settings(
            _env_file=None,
            homebox_api_key="hb_audit" if api_key else None,
            max_request_size_mb=limit_mb,
        ),
    )

    @app.post("/api/upload")
    async def upload(files: Annotated[list[UploadFile], File()]):
        return {"sizes": [file.size for file in files]}

    @app.post("/api/json")
    async def json_body(request: Request):
        return {"size": len(await request.body())}

    return app


async def test_declared_oversize_rejected_without_reading_body():
    consumed = False

    async def content():
        nonlocal consumed
        consumed = True
        yield b"unread"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=make_app()), base_url="http://test") as client:
        response = await client.post("/api/json", headers={"Content-Length": str(1024 * 1024 + 1)}, content=content())
    assert response.status_code == 413
    assert not consumed


@pytest.mark.parametrize("declared_length", [None, "1"])
async def test_streaming_limit_cannot_be_bypassed_by_missing_or_false_length(declared_length):
    chunks_read = 0

    async def content():
        nonlocal chunks_read
        for _ in range(20):
            chunks_read += 1
            yield b"x" * (128 * 1024)

    headers = {} if declared_length is None else {"Content-Length": declared_length}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=make_app()), base_url="http://test") as client:
        response = await client.post("/api/json", headers=headers, content=content())
    assert response.status_code == 413
    assert chunks_read == 9  # Abort at the first chunk crossing 1 MiB.


async def test_multipart_aggregate_limit_closes_spooled_files(monkeypatch):
    files_created = []
    bytes_written = 0
    rolled_to_disk = False

    class TrackedFile(tempfile.SpooledTemporaryFile):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            files_created.append(self)

        def write(self, s):
            nonlocal bytes_written, rolled_to_disk
            bytes_written += len(s)
            result = super().write(s)
            rolled_to_disk |= getattr(self, "_rolled", False)
            return result

    monkeypatch.setattr("starlette.formparsers.SpooledTemporaryFile", TrackedFile)

    async def content():
        for index in range(2):
            yield (
                f'--audit\r\nContent-Disposition: form-data; name="files"; filename="{index}.bin"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
            for _ in range(32):
                yield b"x" * (64 * 1024)
            yield b"\r\n"
        yield b"--audit--\r\n"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=make_app(limit_mb=3)), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/upload",
            headers={"Authorization": "Bearer audit", "Content-Type": "multipart/form-data; boundary=audit"},
            content=content(),
        )

    assert response.status_code == 413
    assert len(files_created) == 2
    assert rolled_to_disk
    assert all(file.closed for file in files_created)
    assert bytes_written <= 3 * 1024 * 1024


@pytest.mark.parametrize("authorization", [None, "Basic invalid", "Bearer "])
async def test_real_app_rejects_missing_multipart_credentials_before_reading(authorization):
    consumed = False

    async def content():
        nonlocal consumed
        consumed = True
        yield b"unread"

    app = create_app(Settings(_env_file=None, homebox_api_key=None, disable_update_check=True))
    headers = {"Content-Type": "multipart/form-data; boundary=audit"}
    if authorization is not None:
        headers["Authorization"] = authorization
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/tools/vision/detect", headers=headers, content=content())
    assert response.status_code == 401
    assert not consumed


@pytest.mark.parametrize("api_key", [False, True])
async def test_small_multipart_uploads_still_succeed(api_key):
    headers = {} if api_key else {"Authorization": "Bearer audit"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=make_app(api_key=api_key)), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/upload", headers=headers, files=[("files", ("one.bin", b"abc")), ("files", ("two.bin", b"abcd"))]
        )
    assert response.status_code == 200
    assert response.json() == {"sizes": [3, 4]}


async def test_body_at_exact_limit_succeeds():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=make_app()), base_url="http://test") as client:
        response = await client.post("/api/json", content=b"x" * (1024 * 1024))
    assert response.status_code == 200
    assert response.json() == {"size": 1024 * 1024}


@pytest.mark.parametrize("field", ["max_upload_size_mb", "max_request_size_mb"])
async def test_upload_limits_cannot_be_disabled_with_zero(field):
    with pytest.raises(ValidationError):
        if field == "max_upload_size_mb":
            Settings(_env_file=None, max_upload_size_mb=0)
        else:
            Settings(_env_file=None, max_request_size_mb=0)
