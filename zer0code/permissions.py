from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class PermissionRule:
    tool_name: str
    risk_level: str
    requires_confirm: bool
    description: str


TOOL_RISK_LEVELS = {
    "bash": "high",
    "write_file": "medium",
    "edit_file": "medium",
    "git_commit": "medium",
    "git_branch": "low",
    "git_status": "low",
    "git_diff": "low",
    "git_log": "low",
    "read_file": "low",
    "glob": "low",
    "grep": "low",
    "web_fetch": "low",
    "subdomain_enum": "medium",
    "port_scan": "high",
    "dns_lookup": "low",
    "whois_lookup": "low",
    "nuclei_scan": "high",
    "dir_fuzz": "high",
    "tech_detect": "low",
    "exploit_search": "low",
    "payload_gen": "medium",
    "reverse_shell": "high",
    "hash_identify": "low",
    "hash_crack": "medium",
    "encoder_decoder": "low",
}

DANGEROUS_PATTERNS = [
    "rm -rf",
    "rm -r /",
    "mkfs",
    "dd if=",
    "> /dev/",
    "chmod 777",
    "curl | sh",
    "wget | sh",
    ":(){ :|:",
    "shutdown",
    "reboot",
    "init 0",
    "systemctl stop",
    "iptables -F",
    "passwd",
    "userdel",
    "DROP TABLE",
    "DROP DATABASE",
    "FORMAT C:",
]


class PermissionManager:
    def __init__(self, confirm_callback: Optional[Callable] = None, auto_approve: bool = False):
        self._confirm = confirm_callback
        self.auto_approve = auto_approve
        self._approved_tools: set[str] = set()
        self._denied_tools: set[str] = set()
        self._session_approvals: dict[str, bool] = {}

    def get_risk_level(self, tool_name: str) -> str:
        return TOOL_RISK_LEVELS.get(tool_name, "medium")

    def check_dangerous_command(self, command: str) -> Optional[str]:
        for pattern in DANGEROUS_PATTERNS:
            if pattern.lower() in command.lower():
                return f"Potentially dangerous pattern detected: '{pattern}'"
        return None

    async def check_permission(self, tool_name: str, args: dict) -> tuple[bool, str]:
        if self.auto_approve:
            return True, ""

        risk = self.get_risk_level(tool_name)

        if risk == "low":
            return True, ""

        if tool_name == "bash" and "command" in args:
            danger = self.check_dangerous_command(args["command"])
            if danger:
                if self._confirm:
                    approved = self._confirm(f"DANGEROUS: {danger}\nCommand: {args['command']}")
                    return approved, danger if not approved else ""
                return False, danger

        if risk == "high":
            cache_key = f"{tool_name}:{hash(str(sorted(args.items())))}"
            if cache_key in self._session_approvals:
                return self._session_approvals[cache_key], ""

            if self._confirm:
                desc = self._format_permission_request(tool_name, args)
                approved = self._confirm(desc)
                self._session_approvals[cache_key] = approved
                return approved, "" if approved else "User denied permission"

        return True, ""

    def _format_permission_request(self, tool_name: str, args: dict) -> str:
        risk = self.get_risk_level(tool_name)
        parts = [f"Tool: {tool_name} [{risk.upper()} risk]"]
        for k, v in args.items():
            val_str = str(v)
            if len(val_str) > 100:
                val_str = val_str[:97] + "..."
            parts.append(f"  {k}: {val_str}")
        return "\n".join(parts)

    def approve_tool_for_session(self, tool_name: str):
        self._approved_tools.add(tool_name)

    def get_all_risks(self) -> dict[str, str]:
        return dict(TOOL_RISK_LEVELS)
