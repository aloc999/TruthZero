# ZER0CODE Swarm — VS Code Extension

Autonomous pentest swarm inside your editor (beta).

## Commands
- `ZER0CODE: Swarm Scan Target` — prompts for an authorized target, runs
  `zer0code scan <t> --scope <t> --swarm` in a terminal
- `ZER0CODE: Show Findings` — opens a SARIF file

## Package & publish (maintainers)
```bash
npm install -g @vscode/vsce
cd deploy/vscode
vsce package        # → zer0code-swarm-0.11.0.vsix
vsce publish        # needs Marketplace PAT (see VS Code docs)
```
Only publish stable milestones. The extension shells out to the `zer0code`
CLI — the user must have it installed (`pip install zer0code`).
