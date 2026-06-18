import asyncio
import pytest
from zer0code.config import ZeroCodeConfig


@pytest.fixture
def config():
    return ZeroCodeConfig(provider="openai", model="gpt-4o", memory_enabled=False)


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
