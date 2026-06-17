from zer0code.tools.base import BaseTool, ToolResult
from zer0code.tools.bash import BashTool
from zer0code.tools.file_ops import ReadFileTool, WriteFileTool, EditFileTool, GlobTool, GrepTool
from zer0code.tools.search import WebFetchTool

ALL_TOOLS = [
    BashTool,
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    GlobTool,
    GrepTool,
    WebFetchTool,
]
