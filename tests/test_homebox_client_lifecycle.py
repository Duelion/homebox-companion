"""Client transport ownership does not require a running Homebox."""

import httpx
import pytest

from homebox_companion import HomeboxClient

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_context_closes_owned_transport():
    async with HomeboxClient(base_url="http://homebox.test") as client:
        transport = client.client
        assert not transport.is_closed
    assert transport.is_closed


@pytest.mark.asyncio
async def test_context_leaves_borrowed_transport_open():
    async with httpx.AsyncClient() as transport:
        async with HomeboxClient(base_url="http://homebox.test", client=transport):
            pass
        assert not transport.is_closed
