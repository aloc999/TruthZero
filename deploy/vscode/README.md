# TRUTHZERO Swarm — VS Code Extension

Autonomous pentest swarm inside your editor (beta).

## Commands
- `TRUTHZERO: Swarm Scan Target` — prompts for an authorized target, runs
  `truthzero scan <t> --scope <t> --swarm` in a terminal
- `TRUTHZERO: Show Findings` — opens a SARIF file

## Package & publish (maintainers)
```bash
npm install -g @vscode/vsce
cd deploy/vscode
vsce package        # → truthzero-swarm-0.11.0.vsix
vsce publish        # needs Marketplace PAT (see VS Code docs)
```
Only publish stable milestones. The extension shells out to the `truthzero`
CLI — the user must have it installed (`pip install truthzero`).
