import asyncio
import inspect
import pytest
from truthzero.config import TruthZeroConfig


@pytest.fixture
def config():
    return TruthZeroConfig(provider="openai", model="gpt-4o", memory_enabled=False)


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: run async test with asyncio")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """Fallback async runner when pytest-asyncio is not installed.

    If pytest-asyncio IS installed it handles the marker itself; this hook
    only fires for unhandled coroutine tests (plugin absent).
    """
    if "asyncio" not in pyfuncitem.keywords:
        return None
    func = pyfuncitem.obj
    if not inspect.iscoroutinefunction(func):
        return None
    kwargs = {name: pyfuncitem.funcargs[name]
              for name in pyfuncitem._fixtureinfo.argnames}
    asyncio.run(func(**kwargs))
    return True
