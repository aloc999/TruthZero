import time
from dataclasses import dataclass, field

PHASES = ["RECON", "ANALYSIS", "EXPLOIT", "REPORT"]

PHASE_OBJECTIVES = {
    "RECON": {
        "name": "Reconnaissance",
        "objectives": [
            "Enumerate subdomains and map attack surface",
            "Port scan and service detection",
            "Technology fingerprinting",
            "Content discovery (directories, files, endpoints)",
            "JavaScript analysis for endpoints and secrets",
            "Identify authentication mechanisms",
        ],
        "tools": ["subdomain_enum", "port_scan", "tech_detect", "dir_fuzz", "web_crawl", "js_analyze", "dns_lookup", "whois_lookup"],
        "transition_criteria": "Move to ANALYSIS when attack surface is mapped and key endpoints identified.",
    },
    "ANALYSIS": {
        "name": "Analysis",
        "objectives": [
            "Review discovered endpoints for vulnerability patterns",
            "Analyze authentication and authorization flows",
            "Check security headers and misconfigurations",
            "Identify input vectors for injection testing",
            "Review API endpoints for IDOR/BOLA",
            "Check for information disclosure",
        ],
        "tools": ["http_replay", "read_file", "web_fetch", "grep"],
        "transition_criteria": "Move to EXPLOIT when potential vulnerabilities are identified and prioritized.",
    },
    "EXPLOIT": {
        "name": "Exploitation",
        "objectives": [
            "Validate identified vulnerabilities with safe PoC",
            "Test injection points (XSS, SQLi, SSRF, etc.)",
            "Attempt authentication bypass",
            "Test for IDOR/authorization flaws",
            "Chain vulnerabilities for maximum impact",
            "Capture evidence (screenshots, responses)",
        ],
        "tools": ["http_replay", "payload_gen", "bash", "screenshot", "web_fetch"],
        "transition_criteria": "Move to REPORT when vulnerabilities are confirmed with PoC evidence.",
    },
    "REPORT": {
        "name": "Reporting",
        "objectives": [
            "Document each finding with severity rating",
            "Write clear steps to reproduce",
            "Include PoC evidence (requests, responses, screenshots)",
            "Assess business impact",
            "Provide remediation recommendations",
            "Generate submission-ready report",
        ],
        "tools": ["write_file", "read_file", "screenshot"],
        "transition_criteria": "Complete when report is ready for submission.",
    },
}


@dataclass
class PipelineState:
    current_phase: str = "RECON"
    phase_start_time: float = field(default_factory=time.time)
    iteration: int = 0
    findings: list = field(default_factory=list)
    completed_objectives: dict = field(default_factory=lambda: {p: [] for p in PHASES})
    phase_history: list = field(default_factory=list)


class BugBountyPipeline:
    def __init__(self):
        self.state = PipelineState()

    @property
    def current_phase(self) -> str:
        return self.state.current_phase

    @property
    def phase_info(self) -> dict:
        return PHASE_OBJECTIVES.get(self.state.current_phase, {})

    def advance_phase(self) -> str:
        idx = PHASES.index(self.state.current_phase)
        if idx < len(PHASES) - 1:
            old = self.state.current_phase
            self.state.phase_history.append({
                "phase": old,
                "duration": time.time() - self.state.phase_start_time,
                "iterations": self.state.iteration,
            })
            self.state.current_phase = PHASES[idx + 1]
            self.state.phase_start_time = time.time()
            self.state.iteration = 0
            return f"Phase: {old} → {self.state.current_phase}"
        return "Already at final phase (REPORT)."

    def set_phase(self, phase: str) -> bool:
        phase = phase.upper()
        if phase in PHASES:
            self.state.current_phase = phase
            self.state.phase_start_time = time.time()
            self.state.iteration = 0
            return True
        return False

    def tick(self):
        self.state.iteration += 1

    def complete_objective(self, objective: str):
        phase = self.state.current_phase
        if objective not in self.state.completed_objectives[phase]:
            self.state.completed_objectives[phase].append(objective)

    def add_finding(self, finding: dict):
        self.state.findings.append({
            "phase": self.state.current_phase,
            "timestamp": time.time(),
            **finding,
        })

    def get_prompt_injection(self) -> str:
        info = PHASE_OBJECTIVES.get(self.state.current_phase, {})
        completed = self.state.completed_objectives.get(self.state.current_phase, [])

        lines = [
            f"CURRENT PHASE: {self.state.current_phase} ({info.get('name', '')})",
            f"Iteration: {self.state.iteration}",
            "Objectives:",
        ]
        for obj in info.get("objectives", []):
            done = "✓" if obj in completed else "○"
            lines.append(f"  {done} {obj}")
        lines.append(f"Recommended tools: {', '.join(info.get('tools', []))}")
        lines.append(f"Transition: {info.get('transition_criteria', '')}")
        if self.state.findings:
            lines.append(f"Findings so far: {len(self.state.findings)}")

        return "\n".join(lines)

    def should_advance(self) -> bool:
        completed = self.state.completed_objectives.get(self.state.current_phase, [])
        total = len(PHASE_OBJECTIVES.get(self.state.current_phase, {}).get("objectives", []))
        if total == 0:
            return False
        return len(completed) >= total * 0.6

    def format_status(self) -> str:
        lines = []
        for phase in PHASES:
            is_current = "→" if phase == self.state.current_phase else " "
            completed = len(self.state.completed_objectives.get(phase, []))
            total = len(PHASE_OBJECTIVES.get(phase, {}).get("objectives", []))
            bar = "█" * completed + "░" * (total - completed)
            lines.append(f"  {is_current} {phase:<10} [{bar}] {completed}/{total}")
        if self.state.findings:
            lines.append(f"\n  Findings: {len(self.state.findings)}")
        return "\n".join(lines)
