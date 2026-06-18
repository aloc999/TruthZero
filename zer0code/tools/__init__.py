from zer0code.tools.base import BaseTool, ToolResult
from zer0code.tools.bash import BashTool
from zer0code.tools.file_ops import ReadFileTool, WriteFileTool, EditFileTool, GlobTool, GrepTool
from zer0code.tools.search import WebFetchTool
from zer0code.tools.git import GitStatusTool, GitDiffTool, GitCommitTool, GitLogTool, GitBranchTool
from zer0code.tools.http_replay import HttpReplayTool
from zer0code.tools.websocket_tool import WebSocketTool
from zer0code.tools.deps import DepsScanTool
from zer0code.tools.clipboard import ClipboardReadTool, ClipboardWriteTool
from zer0code.tools.search_replace import SearchReplaceTool
from zer0code.tools.github import GitHubPRTool, GitHubIssueTool

ALL_TOOLS = [
    BashTool,
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    GlobTool,
    GrepTool,
    WebFetchTool,
    GitStatusTool,
    GitDiffTool,
    GitCommitTool,
    GitLogTool,
    GitBranchTool,
    HttpReplayTool,
    WebSocketTool,
    DepsScanTool,
    ClipboardReadTool,
    ClipboardWriteTool,
    SearchReplaceTool,
    GitHubPRTool,
    GitHubIssueTool,
]
