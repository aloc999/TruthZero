# Security Policy

## Authorized testing only
ZER0CODE is designed exclusively for **authorized security testing**,
**bug bounty programs**, **CTF competitions**, and **educational research**.
You must obtain explicit written permission from the target system owner
before running any scan.

Unauthorized access is illegal under the Computer Fraud and Abuse Act (CFAA),
the Computer Misuse Act, and equivalent laws worldwide.

## Scope safety (defence in depth)
1. **Tool layer** — `ToolchainManager.run()` pre-checks scope, raises on violation.
2. **Executor layer** — `ZeroCoreAgent.execute_tool_call()` re-checks every
   network-capable tool call against `ScopeManager`. Fail closed.
3. **Scheduler layer** — `SwarmScheduler` refuses out-of-scope targets before round 0.

Configure scope via `/scope add <target>` (writes `scope.json`) or
`zer0code scan <target> --scope <target>`.

## Reporting vulnerabilities in ZER0CODE itself
Open a GitHub issue with `[SECURITY]` prefix. Do not post exploits publicly
before a fix is released. The maintainers accept no liability for misuse.
