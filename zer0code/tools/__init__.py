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
from zer0code.tools.burp import BurpImportTool, BurpExportTool
from zer0code.tools.js_analysis import JSAnalysisTool
from zer0code.tools.crawler import CrawlerTool
from zer0code.tools.screenshot import ScreenshotTool
from zer0code.tools.nuclei_mgr import NucleiManagerTool

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
    BurpImportTool,
    BurpExportTool,
    JSAnalysisTool,
    CrawlerTool,
    ScreenshotTool,
    NucleiManagerTool,
]
