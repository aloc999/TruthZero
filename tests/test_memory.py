import pytest
from truthzero.memory.store import MemoryStore
from truthzero.memory.loop_detector import LoopDetector

@pytest.mark.asyncio
async def test_memory_store_init(tmp_path):
    store = MemoryStore(db_path=str(tmp_path / "test.db"))
    await store.init()
    stats = await store.get_stats()
    assert stats["mistakes"] == 0

@pytest.mark.asyncio
async def test_add_mistake(tmp_path):
    store = MemoryStore(db_path=str(tmp_path / "test.db"))
    await store.init()
    await store.add_mistake("testing", "error occurred", "don't do that", "tool_error")
    stats = await store.get_stats()
    assert stats["mistakes"] == 1

@pytest.mark.asyncio
async def test_add_success(tmp_path):
    store = MemoryStore(db_path=str(tmp_path / "test.db"))
    await store.init()
    await store.add_success("testing", "used nmap", "found ports", "recon")
    stats = await store.get_stats()
    assert stats["successes"] == 1

def test_loop_detector_no_loop():
    ld = LoopDetector()
    ld.record_call("bash", {"command": "ls"})
    ld.record_call("bash", {"command": "pwd"})
    assert not ld.is_looping()

def test_loop_detector_detects_loop():
    ld = LoopDetector()
    for _ in range(4):
        ld.record_call("bash", {"command": "ls"})
    assert ld.is_looping()

def test_loop_detector_reset():
    ld = LoopDetector()
    for _ in range(4):
        ld.record_call("bash", {"command": "ls"})
    assert ld.is_looping()
    ld.reset()
    assert not ld.is_looping()
