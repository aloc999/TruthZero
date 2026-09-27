from truthzero.tools.base import BaseTool, ToolResult
from truthzero.tools.bash import BashTool
from truthzero.tools.file_ops import ReadFileTool, WriteFileTool, EditFileTool, GlobTool, GrepTool
from truthzero.tools.search import WebFetchTool
from truthzero.tools.git import GitStatusTool, GitDiffTool, GitCommitTool, GitLogTool, GitBranchTool
from truthzero.tools.http_replay import HttpReplayTool
from truthzero.tools.websocket_tool import WebSocketTool
from truthzero.tools.deps import DepsScanTool
from truthzero.tools.clipboard import ClipboardReadTool, ClipboardWriteTool
from truthzero.tools.search_replace import SearchReplaceTool
from truthzero.tools.github import GitHubPRTool, GitHubIssueTool
from truthzero.tools.burp import BurpImportTool, BurpExportTool
from truthzero.tools.burp_bridge import BurpBridgeTool
from truthzero.tools.js_analysis import JSAnalysisTool
from truthzero.tools.crawler import CrawlerTool
from truthzero.tools.screenshot import ScreenshotTool
from truthzero.tools.nuclei_mgr import NucleiManagerTool
from truthzero.tools.auth_session import AuthSessionTool
from truthzero.tools.oob_server import OOBServerTool
from truthzero.tools.response_diff import ResponseDiffTool
from truthzero.tools.timing_attack import TimingAttackTool
from truthzero.tools.exploit_chain import ExploitChainTool
from truthzero.tools.sqlmap_tool import SqlmapTool
from truthzero.tools.metasploit_tool import MetasploitTool
from truthzero.tools.zap_tool import ZapTool

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
    BurpBridgeTool,
    JSAnalysisTool,
    CrawlerTool,
    ScreenshotTool,
    NucleiManagerTool,
    AuthSessionTool,
    OOBServerTool,
    ResponseDiffTool,
    TimingAttackTool,
    ExploitChainTool,
    SqlmapTool,
    MetasploitTool,
    ZapTool,
]
