import pytest

from truthzero.tools.bash import BashTool
from truthzero.tools.file_ops import GlobTool, ReadFileTool, WriteFileTool


@pytest.mark.asyncio
async def test_bash_echo():
    tool = BashTool()
    result = await tool.execute(command="echo hello")
    assert result.success
    assert "hello" in result.output

@pytest.mark.asyncio
async def test_bash_timeout():
    tool = BashTool()
    result = await tool.execute(command="sleep 0.1 && echo done", timeout=5)
    assert result.success

@pytest.mark.asyncio
async def test_read_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("line1\nline2\nline3")
    tool = ReadFileTool()
    result = await tool.execute(file_path=str(f))
    assert result.success
    assert "line1" in result.output

@pytest.mark.asyncio
async def test_write_file(tmp_path):
    f = tmp_path / "out.txt"
    tool = WriteFileTool()
    result = await tool.execute(file_path=str(f), content="test content")
    assert result.success
    assert f.read_text() == "test content"

@pytest.mark.asyncio
async def test_glob(tmp_path):
    (tmp_path / "a.py").touch()
    (tmp_path / "b.py").touch()
    (tmp_path / "c.txt").touch()
    tool = GlobTool()
    result = await tool.execute(pattern="*.py", path=str(tmp_path))
    assert result.success
    assert "a.py" in result.output
    assert "b.py" in result.output

def test_tool_schema():
    schema = BashTool.schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "bash"
