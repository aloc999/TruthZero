import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import click
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from zer0code import __codename__, __version__
from zer0code.agent import ZeroCoreAgent
from zer0code.config import CONFIG_DIR, ZeroCodeConfig
from zer0code.cost import CostTracker
from zer0code.permissions import PermissionManager
from zer0code.session import SessionManager
from zer0code.ui.terminal import TerminalUI
from zer0code.ui.diff import DiffRenderer
from zer0code.tools import ALL_TOOLS
from zer0code.tools.security import SECURITY_TOOLS
from zer0code.tools.git import GitStatusTool, GitDiffTool, GitCommitTool, GitLogTool, GitBranchTool
from zer0code.branching import ConversationBrancher

VALID_PROVIDERS = ["openai", "anthropic", "deepseek", "ollama"]

GIT_TOOLS = [GitStatusTool, GitDiffTool, GitCommitTool, GitLogTool, GitBranchTool]


class _PermissionPending(Exception):
    def __init__(self, description):
        self.description = description

def _safe_input(console, prompt_text: str):
    return None


def get_history_path() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR / "history.txt"


async def handle_slash_command(
    command: str, agent: ZeroCoreAgent, config: ZeroCodeConfig, ui: TerminalUI, session_mgr: SessionManager
) -> bool:
    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "/help":
        ui.show_help()

    elif cmd == "/clear":
        agent.reset()
        ui.console.print(Text("  Conversation cleared.", style="bold green"))

    elif cmd == "/memory":
        if agent.memory_store:
            try:
                stats = await agent.memory_store.get_stats()
                all_mem = await agent.memory_store.get_all_memories(limit=20)
                memories = []
                for m in all_mem.get("mistakes", []):
                    memories.append({"category": "mistake", "content": m.get("lesson", ""), "source": "auto"})
                for s in all_mem.get("successes", []):
                    memories.append({"category": "success", "content": s.get("approach", ""), "source": "auto"})
                for k in all_mem.get("knowledge", []):
                    memories.append({"category": k.get("category", "general"), "content": k.get("value", ""), "source": k.get("source", "")})
                ui.show_memories(memories)
                ui.console.print(Text(f"\n  Stats: {stats}", style="dim"))
            except Exception as e:
                ui.render_error(f"Memory error: {e}")
        else:
            ui.console.print(Text("  Memory system not enabled.", style="dim"))

    elif cmd == "/tools":
        tools_info = []
        for name, tool in agent.tool_registry.items():
            risk = "low"
            if agent.permissions:
                risk = agent.permissions.get_risk_level(name)
            tools_info.append({"name": name, "description": getattr(tool, "description", ""), "risk": risk})
        ui.show_tools(tools_info)

    elif cmd == "/config":
        table = Table(title="Configuration", border_style="cyan")
        table.add_column("Setting", style="bold cyan")
        table.add_column("Value", style="white")
        table.add_row("Provider", config.provider)
        table.add_row("Model", config.model)
        table.add_row("API Key", "***set***" if config.api_key else "[red]not set[/]")
        table.add_row("Memory", str(config.memory_enabled))
        table.add_row("Max Tokens", str(config.max_context_tokens))
        table.add_row("Theme", config.theme)
        table.add_row("Session ID", agent.session_id or "none")
        table.add_row("Total Cost", agent.total_cost)
        table.add_row("Proxy", f"{config.security_tools.proxy_host}:{config.security_tools.proxy_port}" if config.security_tools.use_proxy else "disabled")
        ui.console.print(table)

    elif cmd == "/model":
        PROVIDER_MODELS = {
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini"],
            "anthropic": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
            "deepseek": ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-pro"],
            "ollama": ["qwen2.5-coder:14b", "llama3.1", "deepseek-coder-v2", "codellama"],
        }
        if args:
            config.model = args.strip()
            config.save()
            await agent.initialize()
            ui.console.print(Text(f"  Model switched to: {config.model}", style="bold green"))
        else:
            models = PROVIDER_MODELS.get(config.provider, [])
            table = Table(title=f"Models ({config.provider})", border_style="cyan", expand=False)
            table.add_column("#", style="bold cyan", width=4)
            table.add_column("Model", style="white")
            table.add_column("", style="bold green", width=3)
            for i, m in enumerate(models, 1):
                marker = " ◀" if m == config.model else ""
                table.add_row(str(i), m, marker)
            ui.console.print(table)
            ui.console.print(Text(f"  /model <name> or /model <number> to switch", style="dim"))
            if args and args.strip().isdigit():
                idx = int(args.strip()) - 1
                if 0 <= idx < len(models):
                    config.model = models[idx]
                    config.save()
                    await agent.initialize()
                    ui.console.print(Text(f"  Model switched to: {config.model}", style="bold green"))

    elif cmd == "/provider":
        if args:
            provider = args.strip().lower()
            if provider.isdigit():
                idx = int(provider) - 1
                providers = list(VALID_PROVIDERS)
                if 0 <= idx < len(providers):
                    provider = providers[idx]
            if provider in VALID_PROVIDERS:
                config.provider = provider
                config.save()
                await agent.initialize()
                ui.console.print(Text(f"  Provider switched to: {config.provider}", style="bold green"))
            else:
                ui.console.print(Text(f"  Valid providers: {', '.join(VALID_PROVIDERS)}", style="red"))
        else:
            table = Table(title="Providers", border_style="cyan", expand=False)
            table.add_column("#", style="bold cyan", width=4)
            table.add_column("Provider", style="white")
            table.add_column("", style="bold green", width=3)
            for i, p in enumerate(VALID_PROVIDERS, 1):
                marker = " ◀" if p == config.provider else ""
                table.add_row(str(i), p, marker)
            ui.console.print(table)
            ui.console.print(Text(f"  /provider <name> or /provider <number> to switch", style="dim"))

    elif cmd == "/switch":
        _PM = {
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini"],
            "anthropic": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
            "deepseek": ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-pro"],
            "ollama": ["qwen2.5-coder:14b", "llama3.1", "deepseek-coder-v2"],
        }
        _EK = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "deepseek": "DEEPSEEK_API_KEY", "ollama": None}
        if args:
            parts = args.strip().split(maxsplit=1)
            prov = parts[0].lower()
            if prov not in VALID_PROVIDERS:
                ui.console.print(Text(f"  Valid: {', '.join(VALID_PROVIDERS)}", style="red"))
                return False
            ek = _EK.get(prov)
            if ek and not os.environ.get(ek):
                ui.console.print(Text(f"\n  ✗ {ek} not set. Type your API key below (Enter to cancel):\n", style="bold red"))
                agent._switch_pending = {"step": "enter_key", "provider": prov, "env_key": ek, "model": parts[1].strip() if len(parts) > 1 else None, "pm": _PM}
                return False
            config.provider = prov
            config.model = parts[1].strip() if len(parts) > 1 else (_PM.get(prov, [""])[0])
            config.save()
            await agent.initialize()
            ui.console.print(Text(f"  ✓ Switched to: {config.provider}/{config.model}", style="bold green"))
        else:
            ui.console.print(Text(f"\n  Current: {config.provider}/{config.model}\n", style="bold cyan"))
            provs = list(_PM.keys())
            for i, p in enumerate(provs, 1):
                marker = " ◀ current" if p == config.provider else ""
                ek = _EK.get(p)
                ks = (" ✓" if os.environ.get(ek) else " ✗ no key") if ek else ""
                line = Text()
                line.append(f"  [{i}] ", style="bold cyan")
                line.append(f"{p}", style="bold white")
                line.append(ks, style="green" if "✓" in ks else "red")
                line.append(marker, style="bold green")
                ui.console.print(line)
            ui.console.print(Text(f"\n  Type a number below (Enter to cancel):\n", style="dim"))
            agent._switch_pending = {"step": "select_provider", "providers": provs, "pm": _PM, "ek": _EK}

    elif cmd == "/theme":
        if args:
            ui.set_theme(args.strip())
        else:
            from zer0code.ui.themes import THEMES
            ui.console.print(Text(f"  Available themes: {', '.join(THEMES.keys())}", style="dim"))

    elif cmd == "/compact":
        old_len = len(agent.conversation_history)
        agent.conversation_history = await agent.compactor.compact(agent.conversation_history)
        new_len = len(agent.conversation_history)
        ui.console.print(Text(f"  Compacted: {old_len} -> {new_len} messages", style="bold green"))

    elif cmd == "/cost":
        summary = agent.cost_tracker.summary()
        table = Table(title="Cost Summary", border_style="cyan")
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")
        table.add_row("Total Tokens", f"{summary['total_tokens']:,}")
        table.add_row("Input Tokens", f"{summary['input_tokens']:,}")
        table.add_row("Output Tokens", f"{summary['output_tokens']:,}")
        table.add_row("Total Cost", agent.total_cost)
        table.add_row("Requests", str(summary['requests']))
        ui.console.print(table)

    elif cmd == "/session":
        if args == "list":
            sessions = await session_mgr.list_sessions()
            if sessions:
                table = Table(title="Sessions", border_style="cyan")
                table.add_column("ID", style="bold cyan")
                table.add_column("Title", style="white")
                table.add_column("Messages", style="dim")
                table.add_column("Updated", style="dim")
                table.add_column("Model", style="dim")
                for s in sessions:
                    updated = datetime.fromtimestamp(s.updated_at).strftime("%Y-%m-%d %H:%M")
                    table.add_row(s.session_id, s.title, str(s.message_count), updated, s.model)
                ui.console.print(table)
            else:
                ui.console.print(Text("  No sessions found.", style="dim"))
        elif args.startswith("load "):
            sid = args[5:].strip()
            if await agent.load_session(sid):
                ui.console.print(Text(f"  Session {sid} loaded ({agent.message_count} messages)", style="bold green"))
            else:
                ui.console.print(Text(f"  Session {sid} not found.", style="red"))
        elif args.startswith("title "):
            title = args[6:].strip()
            if agent.session_id:
                await session_mgr.update_title(agent.session_id, title)
                ui.console.print(Text(f"  Session title updated: {title}", style="bold green"))
        else:
            ui.console.print(Text(f"  Current session: {agent.session_id or 'none'}", style="dim"))
            ui.console.print(Text("  Usage: /session list | /session load <id> | /session title <name>", style="dim"))

    elif cmd == "/skill":
        from zer0code.skills.loader import SkillLoader
        loader = SkillLoader()
        if not args:
            by_cat = loader.list_by_category()
            for category, skills in by_cat.items():
                table = Table(title=category, border_style="magenta", expand=True)
                table.add_column("Skill", style="bold magenta", width=22)
                table.add_column("Description", style="white")
                table.add_column("Lines", style="dim", width=6)
                for skill in skills:
                    table.add_row(
                        skill["name"],
                        skill.get("description", "")[:60],
                        str(skill.get("lines", "")),
                    )
                ui.console.print(table)
            ui.console.print(Text(f"\n  {loader.count} skills ({loader.builtin_count} builtin, {loader.custom_count} custom)", style="dim"))
            ui.console.print(Text("  Usage: /skill <name> to load | /skill search <query> | /skill info <name>", style="dim"))
        elif args.startswith("search "):
            query = args[7:].strip()
            results = loader.search(query)
            if results:
                for s in results:
                    ui.console.print(Text(f"  {s['name']}: {s.get('description', '')[:80]}", style="white"))
            else:
                ui.console.print(Text(f"  No skills matching '{query}'", style="dim"))
        elif args.startswith("info "):
            skill_name = args[5:].strip()
            skill = loader.get_skill(skill_name)
            if skill:
                ui.console.print(Text(f"\n  {skill.get('title', skill['name'])}", style="bold magenta"))
                ui.console.print(Text(f"  Category: {skill.get('category', 'unknown')}", style="dim"))
                ui.console.print(Text(f"  Lines: {skill.get('lines', '?')} | Custom: {skill.get('custom', False)}", style="dim"))
                ui.console.print(Text(f"  {skill.get('description', '')}\n", style="white"))
                preview = skill.get("content", "")[:500]
                if len(skill.get("content", "")) > 500:
                    preview += "\n..."
                ui.console.print(Markdown(preview))
            else:
                ui.console.print(Text(f"  Skill '{skill_name}' not found.", style="red"))
        elif args.startswith("create "):
            skill_name = args[7:].strip()
            filepath = loader.create_custom_skill(skill_name, skill_name.replace("-", " ").title(), "Add your methodology here.\n")
            ui.console.print(Text(f"  Created custom skill: {filepath}", style="bold green"))
            ui.console.print(Text(f"  Edit the file to add your methodology.", style="dim"))
        else:
            skill_name = args.strip()
            skill = loader.get_skill(skill_name)
            if skill:
                agent.conversation_history.append({
                    "role": "system",
                    "content": f"LOADED SKILL: {skill.get('title', skill['name'])}\n\n{skill['system_prompt_addition']}",
                })
                ui.console.print(Text(f"  Skill loaded: {skill.get('title', skill['name'])} ({skill.get('lines', '?')} lines)", style="bold green"))
                ui.console.print(Text(f"  {skill.get('description', '')}", style="dim"))
            else:
                matches = loader.search(skill_name)
                if matches:
                    ui.console.print(Text(f"  Skill '{skill_name}' not found. Did you mean:", style="yellow"))
                    for m in matches[:5]:
                        ui.console.print(Text(f"    - {m['name']}", style="dim"))
                else:
                    ui.console.print(Text(f"  Skill '{skill_name}' not found. Type /skill to list all.", style="red"))

    elif cmd == "/persona":
        from zer0code.personas import PersonaManager
        pm = PersonaManager()
        if args:
            persona = pm.get_persona(args.strip())
            if persona:
                agent.conversation_history.append({"role": "system", "content": persona.system_prompt})
                ui.console.print(Text(f"  Persona: {persona.title}", style="bold green"))
                ui.console.print(Text(f"  {persona.description}", style="dim"))
            else:
                ui.console.print(Text(f"  Unknown persona. Available: {', '.join(pm.list_personas())}", style="red"))
        else:
            table = Table(title="Agent Personas", border_style="magenta")
            table.add_column("Name", style="bold magenta")
            table.add_column("Title", style="white")
            table.add_column("Risk", style="dim")
            for name in pm.list_personas():
                p = pm.get_persona(name)
                table.add_row(name, p.title, p.risk_tolerance)
            ui.console.print(table)

    elif cmd == "/template" or cmd == "/t":
        from zer0code.templates import TemplateManager
        tm = TemplateManager()
        if not args:
            table = Table(title="Prompt Templates", border_style="cyan")
            table.add_column("Name", style="bold cyan", width=18)
            table.add_column("Description", style="white")
            for name, desc in tm.list_templates():
                table.add_row(name, desc[:60])
            ui.console.print(table)
            ui.console.print(Text("  Usage: /template <name> <target>", style="dim"))
        else:
            parts = args.strip().split(maxsplit=1)
            tpl_name = parts[0]
            tpl_args = parts[1] if len(parts) > 1 else ""
            rendered = tm.render(tpl_name, target=tpl_args, input=tpl_args)
            if rendered:
                ui.console.print(Text(f"  Running template: {tpl_name}", style="bold cyan"))
                try:
                    response = await agent.run(rendered)
                    if response:
                        ui.render_response(response)
                except Exception as e:
                    ui.render_error(str(e))
            else:
                ui.console.print(Text(f"  Template '{tpl_name}' not found.", style="red"))

    elif cmd == "/proxy":
        from zer0code.proxy import ProxyManager
        pm = ProxyManager()
        if args == "on" or args == "enable":
            pm.enable()
            ui.console.print(Text(f"  Proxy enabled: {pm.config.url}", style="bold green"))
        elif args == "off" or args == "disable":
            pm.disable()
            ui.console.print(Text("  Proxy disabled.", style="bold green"))
        elif args == "test":
            ok, msg = await pm.test_connection()
            style = "bold green" if ok else "red"
            ui.console.print(Text(f"  {msg}", style=style))
        else:
            status = pm.status()
            ui.console.print(Text(f"  Proxy: {'ACTIVE' if status['enabled'] else 'disabled'}", style="bold green" if status['enabled'] else "dim"))
            if status['proxy_url']:
                ui.console.print(Text(f"  URL: {status['proxy_url']}", style="dim"))

    elif cmd == "/branch":
        if not args or args == "list":
            branches = agent.brancher.list_branches()
            table = Table(title="Conversation Branches", border_style="cyan")
            table.add_column("Name", style="bold cyan")
            table.add_column("Messages", style="dim")
            table.add_column("Parent", style="dim")
            table.add_column("", style="bold green")
            for b in branches:
                marker = " <--" if b["current"] else ""
                table.add_row(b["name"], str(b["messages"]), b["parent"], marker)
            ui.console.print(table)
        elif args.startswith("create "):
            name = args[7:].strip()
            created = agent.brancher.create_branch(name)
            agent.brancher.switch_branch(created)
            agent.conversation_history = agent.brancher.current_messages
            ui.console.print(Text(f"  Branch created and switched to: {created}", style="bold green"))
        elif args.startswith("switch "):
            name = args[7:].strip()
            if agent.brancher.switch_branch(name):
                agent.conversation_history = agent.brancher.current_messages
                ui.console.print(Text(f"  Switched to branch: {name}", style="bold green"))
            else:
                ui.console.print(Text(f"  Branch '{name}' not found.", style="red"))
        elif args.startswith("merge "):
            source = args[6:].strip()
            if agent.brancher.merge_branch(source):
                agent.conversation_history = agent.brancher.current_messages
                ui.console.print(Text(f"  Merged '{source}' into current branch.", style="bold green"))
            else:
                ui.console.print(Text(f"  Merge failed.", style="red"))
        elif args.startswith("delete "):
            name = args[7:].strip()
            if agent.brancher.delete_branch(name):
                ui.console.print(Text(f"  Branch '{name}' deleted.", style="bold green"))
            else:
                ui.console.print(Text(f"  Cannot delete '{name}'.", style="red"))
        else:
            ui.console.print(Text("  Usage: /branch [list|create|switch|merge|delete] <name>", style="dim"))

    elif cmd == "/export":
        filepath = args.strip() if args else f"zer0code-report-{int(time.time())}.md"
        fmt = "html" if filepath.endswith(".html") else "md"
        metadata = {
            "provider": config.provider, "model": config.model,
            "session_id": agent.session_id,
            "total_tokens": agent.total_tokens, "total_cost": agent.total_cost,
        }
        saved = agent.exporter.save(agent.conversation_history, filepath, format=fmt, metadata=metadata)
        ui.console.print(Text(f"  Exported to: {saved}", style="bold green"))

    elif cmd == "/undo" or cmd == "/rollback":
        if args == "all":
            restored = agent.rollback.rollback_all()
            if restored:
                ui.console.print(Text(f"  Restored {len(restored)} files.", style="bold green"))
                for f in restored:
                    ui.console.print(Text(f"    - {f}", style="dim"))
            else:
                ui.console.print(Text("  No changes to rollback.", style="dim"))
        elif args == "list":
            changes = agent.rollback.list_changes()
            if changes:
                for c in changes:
                    ui.console.print(Text(f"  {c['filepath']}", style="white"))
            else:
                ui.console.print(Text("  No tracked changes.", style="dim"))
        elif args:
            if agent.rollback.rollback(args.strip()):
                ui.console.print(Text(f"  Restored: {args.strip()}", style="bold green"))
            else:
                ui.console.print(Text(f"  No snapshot for: {args.strip()}", style="red"))
        else:
            ui.console.print(Text("  Usage: /undo [all|list|<filepath>]", style="dim"))

    elif cmd == "/plugin":
        from zer0code.plugins import PluginManager
        pm = PluginManager()
        if not args or args == "list":
            pm.load_all()
            plugins = pm.list_plugins()
            if plugins:
                table = Table(title="Plugins", border_style="magenta")
                table.add_column("Name", style="bold magenta")
                table.add_column("Version", style="dim")
                table.add_column("Tools", style="cyan")
                table.add_column("Description", style="white")
                for p in plugins:
                    table.add_row(p["name"], p["version"], str(p["tools"]), p["description"][:40])
                ui.console.print(table)
            else:
                ui.console.print(Text("  No plugins installed. Dir: ~/.zer0code/plugins/", style="dim"))
        elif args.startswith("create "):
            name = args[7:].strip()
            filepath = pm.create_template(name)
            ui.console.print(Text(f"  Plugin template created: {filepath}", style="bold green"))
        elif args == "load":
            pm.load_all()
            for tool in pm.get_all_tools():
                agent.register_tool(tool)
            ui.console.print(Text(f"  Loaded {pm.count} plugins with {len(pm.get_all_tools())} tools.", style="bold green"))

    elif cmd == "/serve":
        from zer0code.server import APIServer
        if args == "stop":
            ui.console.print(Text("  API server stopped.", style="bold green"))
        elif args == "start" or not args:
            srv = APIServer()
            url = srv.start(agent=agent)
            ui.console.print(Text(f"  API server running at {url}", style="bold green"))
            ui.console.print(Text("  POST /api/chat | GET /api/health | GET /api/status", style="dim"))

    elif cmd == "/budget":
        if args:
            try:
                budget = float(args.strip().replace("$", ""))
                agent.token_budget = budget
                ui.console.print(Text(f"  Token budget set: ${budget:.2f}", style="bold green"))
            except ValueError:
                ui.console.print(Text("  Usage: /budget <amount> (e.g., /budget 5.00)", style="red"))
        else:
            if agent.token_budget > 0:
                ui.console.print(Text(f"  Budget: ${agent.token_budget:.2f} | Spent: {agent.total_cost} | Remaining: ${max(0, agent.token_budget - agent.cost_tracker.total_cost):.4f}", style="dim"))
            else:
                ui.console.print(Text("  No budget set. Usage: /budget <amount>", style="dim"))

    elif cmd == "/creds":
        from zer0code.credentials import CredentialManager
        cm = CredentialManager()
        if not args or args == "list":
            names = cm.list_names()
            if names:
                for n in names:
                    ui.console.print(Text(f"  - {n}", style="cyan"))
            else:
                ui.console.print(Text("  No stored credentials.", style="dim"))
        elif args.startswith("set "):
            parts = args[4:].strip().split(maxsplit=1)
            if len(parts) == 2:
                cm.set(parts[0], parts[1])
                ui.console.print(Text(f"  Credential '{parts[0]}' saved.", style="bold green"))
            else:
                ui.console.print(Text("  Usage: /creds set <name> <value>", style="dim"))
        elif args.startswith("get "):
            name = args[4:].strip()
            val = cm.get(name)
            if val:
                ui.console.print(Text(f"  {name} = {val[:4]}{'*' * (len(val)-4)}", style="cyan"))
            else:
                ui.console.print(Text(f"  Credential '{name}' not found.", style="red"))
        elif args.startswith("delete "):
            name = args[7:].strip()
            cm.delete(name)
            ui.console.print(Text(f"  Credential '{name}' deleted.", style="bold green"))

    elif cmd == "/lsp":
        from zer0code.lsp import LSPClient
        filepath = args.strip() if args else ""
        if not filepath:
            ui.console.print(Text("  Usage: /lsp <filepath> — get code diagnostics", style="dim"))
        else:
            diagnostics = await LSPClient.get_diagnostics_simple(filepath)
            if diagnostics:
                for d in diagnostics:
                    sev = d.get("severity", "info")
                    style = "red" if sev == "error" else "yellow" if sev == "warning" else "dim"
                    ui.console.print(Text(f"  {d['file']}:{d['line']} [{sev}] {d['message']}", style=style))
            else:
                ui.console.print(Text(f"  No diagnostics for {filepath}", style="bold green"))

    elif cmd == "/report":
        from zer0code.reports import ReportGenerator
        rg = ReportGenerator()
        if not args:
            templates = rg.list_templates()
            table = Table(title="Report Templates", border_style="cyan")
            table.add_column("Key", style="bold cyan")
            table.add_column("Name", style="white")
            table.add_column("Description", style="dim")
            for t in templates:
                table.add_row(t["key"], t["name"], t["description"][:50])
            ui.console.print(table)
            ui.console.print(Text("  Usage: /report <template> [output_file]", style="dim"))
        else:
            parts = args.strip().split(maxsplit=1)
            tpl = parts[0]
            outfile = parts[1] if len(parts) > 1 else f"report-{tpl}-{int(time.time())}.md"
            metadata = {"provider": config.provider, "model": config.model, "session_id": agent.session_id}
            content = rg.generate(tpl, agent.conversation_history, metadata)
            Path(outfile).write_text(content, encoding="utf-8")
            ui.console.print(Text(f"  Report saved: {outfile}", style="bold green"))

    elif cmd == "/share":
        from zer0code.sharing import TeamSharing
        ts = TeamSharing()
        if args.startswith("export"):
            outfile = args[7:].strip() if len(args) > 7 else f"zer0code-pack-{int(time.time())}.z0pack"
            path = ts.export_pack(outfile)
            ui.console.print(Text(f"  Pack exported: {path}", style="bold green"))
        elif args.startswith("import"):
            packfile = args[7:].strip()
            result = ts.import_pack(packfile)
            if "error" in result:
                ui.console.print(Text(f"  {result['error']}", style="red"))
            else:
                ui.console.print(Text(f"  Imported {len(result['files'])} files, skipped {len(result['skipped'])}", style="bold green"))
        else:
            info = ts.list_exportable()
            ui.console.print(Text(f"  Exportable: {info['skills']} skills, {info['plugins']} plugins, config: {info['config']}", style="dim"))
            ui.console.print(Text("  Usage: /share export [file] | /share import <file>", style="dim"))

    elif cmd == "/compare":
        if not args:
            ui.console.print(Text("  Usage: /compare <prompt> — sends to multiple models", style="dim"))
        else:
            from zer0code.compare import ModelComparator
            from zer0code.providers import get_provider
            mc = ModelComparator()
            models = [
                {"provider": "deepseek", "model": "deepseek-chat"},
                {"provider": "openai", "model": "gpt-4o-mini"},
            ]
            ui.console.print(Text("  Comparing models...", style="dim"))
            try:
                results = await mc.compare(args, models, provider_factory=lambda p, **kw: get_provider(p, **kw, api_key=config.api_key or ""))
                output = ModelComparator.format_results(results)
                ui.render_response(output)
            except Exception as e:
                ui.render_error(str(e))

    elif cmd == "/update":
        from zer0code.updater import UpdateChecker
        from zer0code import __version__
        ui.console.print(Text("  Checking for updates...", style="dim"))
        info = await UpdateChecker.check(__version__)
        if info:
            ui.console.print(Text(f"  {UpdateChecker.format_update_message(info)}", style="bold yellow"))
        else:
            ui.console.print(Text(f"  ZER0CODE v{__version__} is up to date.", style="bold green"))

    elif cmd == "/cache":
        if hasattr(agent, '_cache') and agent._cache:
            stats = agent._cache.stats
            ui.console.print(Text(f"  Cache: {stats['cached']} entries | Hit rate: {stats['hit_rate']} | Hits: {stats['hits']} | Misses: {stats['misses']}", style="dim"))
        else:
            ui.console.print(Text("  Cache not enabled.", style="dim"))

    elif cmd == "/step":
        if not hasattr(agent, '_step_mode'):
            agent._step_mode = False
        agent._step_mode = not agent._step_mode
        mode = "ON" if agent._step_mode else "OFF"
        ui.console.print(Text(f"  Step mode: {mode} — {'each tool call requires approval' if agent._step_mode else 'tools execute automatically'}", style="bold green"))

    elif cmd == "/prompt":
        if args:
            agent._custom_prompt = args.strip()
            ui.console.print(Text("  Custom system prompt set.", style="bold green"))
        else:
            if hasattr(agent, '_custom_prompt') and agent._custom_prompt:
                ui.console.print(Text(f"  Current custom prompt: {agent._custom_prompt[:100]}...", style="dim"))
            else:
                ui.console.print(Text("  No custom prompt set. Usage: /prompt <additional instructions>", style="dim"))

    elif cmd == "/search":
        if not args:
            ui.console.print(Text("  Usage: /search <keyword> — search conversation history", style="dim"))
        else:
            query = args.strip().lower()
            matches = []
            for i, m in enumerate(agent.conversation_history):
                content = str(m.get("content", ""))
                if query in content.lower():
                    role = m.get("role", "?")
                    snippet = content[:100].replace("\n", " ")
                    matches.append(f"  [{i}] {role}: {snippet}")
            if matches:
                ui.console.print(Text(f"  Found {len(matches)} matches:", style="bold green"))
                for m in matches[:15]:
                    ui.console.print(Text(m, style="dim"))
            else:
                ui.console.print(Text(f"  No matches for '{args.strip()}'", style="dim"))

    elif cmd == "/preview":
        if args:
            filepath = args.strip()
            if filepath.endswith(".html") and os.path.exists(filepath):
                import webbrowser
                webbrowser.open(f"file://{os.path.abspath(filepath)}")
                ui.console.print(Text(f"  Opened {filepath} in browser.", style="bold green"))
            elif os.path.exists(filepath):
                try:
                    content = Path(filepath).read_text()[:2000]
                    ui.render_response(content)
                except Exception as e:
                    ui.render_error(str(e))
            else:
                ui.console.print(Text(f"  File not found: {filepath}", style="red"))
        else:
            ui.console.print(Text("  Usage: /preview <filepath> — preview file or open HTML in browser", style="dim"))

    elif cmd == "/env":
        import shutil
        env_info = {
            "shell": os.environ.get("SHELL", "unknown"),
            "user": os.environ.get("USER", "unknown"),
            "home": os.environ.get("HOME", "unknown"),
            "cwd": os.getcwd(),
            "path_dirs": len(os.environ.get("PATH", "").split(":")),
            "python": shutil.which("python3") or shutil.which("python") or "not found",
            "git": shutil.which("git") or "not found",
            "nmap": shutil.which("nmap") or "not found",
            "ffuf": shutil.which("ffuf") or "not found",
            "nuclei": shutil.which("nuclei") or "not found",
        }
        table = Table(title="Shell Environment", border_style="cyan")
        table.add_column("Key", style="bold cyan")
        table.add_column("Value", style="white")
        for k, v in env_info.items():
            table.add_row(k, str(v))
        ui.console.print(table)

    elif cmd == "/init":
        from zer0code.init_project import ProjectInitializer
        pi = ProjectInitializer()
        filepath = pi.save()
        ui.console.print(Text(f"  Generated: {filepath}", style="bold green"))
        content = Path(filepath).read_text()[:500]
        ui.console.print(Text(content, style="dim"))
        agent.project_context.load_instructions()
        ui.console.print(Text("\n  Project context loaded into agent.", style="bold green"))

    elif cmd == "/doctor":
        from zer0code.doctor import Doctor
        doc = Doctor()
        results = await doc.run_all()
        table = Table(title="System Health Check", border_style="cyan")
        table.add_column("Check", style="bold cyan", width=18)
        table.add_column("Status", width=6)
        table.add_column("Detail", style="dim")
        for check in results:
            status = check["status"]
            if status == "pass":
                icon = Text("PASS", style="bold green")
            elif status == "warn":
                icon = Text("WARN", style="bold yellow")
            else:
                icon = Text("FAIL", style="bold red")
            table.add_row(check["name"], icon, check["detail"])
        ui.console.print(table)
        ui.console.print(Text(f"\n  {doc.summary}", style="dim"))

    elif cmd == "/login":
        from zer0code.credentials import CredentialManager
        cm = CredentialManager()
        if not args:
            ui.console.print(Text("  Set API keys interactively:", style="bold cyan"))
            ui.console.print(Text("  /login openai <key>", style="dim"))
            ui.console.print(Text("  /login anthropic <key>", style="dim"))
            ui.console.print(Text("  /login deepseek <key>", style="dim"))
            ui.console.print(Text("  Keys are stored encrypted in ~/.zer0code/credentials.enc", style="dim"))
        else:
            parts = args.strip().split(maxsplit=1)
            if len(parts) == 2:
                provider_name = parts[0].lower()
                key_value = parts[1].strip()
                env_map = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}
                env_name = env_map.get(provider_name)
                if env_name:
                    cm.set(env_name, key_value)
                    os.environ[env_name] = key_value
                    ui.console.print(Text(f"  {provider_name} API key saved and activated.", style="bold green"))
                else:
                    ui.console.print(Text(f"  Unknown provider: {provider_name}", style="red"))
            else:
                ui.console.print(Text("  Usage: /login <provider> <api_key>", style="dim"))

    elif cmd == "/approve":
        if args:
            tool_name = args.strip()
            if agent.permissions:
                agent.permissions.approve_tool_for_session(tool_name)
                ui.console.print(Text(f"  Tool '{tool_name}' approved for this session.", style="bold green"))
        else:
            ui.console.print(Text("  Usage: /approve <tool_name> — auto-approve a tool for this session", style="dim"))
            if agent.permissions:
                approved = agent.permissions._approved_tools
                if approved:
                    ui.console.print(Text(f"  Currently approved: {', '.join(approved)}", style="dim"))

    elif cmd == "/diff":
        if not hasattr(agent, '_diff_approval'):
            agent._diff_approval = False
        agent._diff_approval = not agent._diff_approval
        mode = "ON" if agent._diff_approval else "OFF"
        ui.console.print(Text(f"  Diff approval: {mode} — {'edits require confirmation' if agent._diff_approval else 'edits apply automatically'}", style="bold green"))

    elif cmd == "/turns":
        if args:
            try:
                turns = int(args.strip())
                agent.max_turns = max(1, min(turns, 100))
                ui.console.print(Text(f"  Max turns set to: {agent.max_turns}", style="bold green"))
            except ValueError:
                ui.console.print(Text("  Usage: /turns <number> (1-100)", style="dim"))
        else:
            ui.console.print(Text(f"  Max turns: {agent.max_turns}", style="dim"))

    elif cmd == "/files":
        if agent.file_index:
            if args:
                results = agent.file_index.search(args.strip())
                if results:
                    for r in results[:20]:
                        ui.console.print(Text(f"  {r}", style="dim"))
                    ui.console.print(Text(f"  {len(results)} matches", style="dim"))
                else:
                    ui.console.print(Text(f"  No files matching '{args.strip()}'", style="dim"))
            else:
                tree = agent.file_index.get_tree()
                ui.console.print(Text(tree, style="dim"))
                ui.console.print(Text(f"\n  {agent.file_index.file_count} files indexed", style="dim"))
        else:
            ui.console.print(Text("  No file index available.", style="dim"))

    elif cmd == "/scope":
        if not hasattr(agent, '_scope'):
            from zer0code.scope import ScopeManager
            agent._scope = ScopeManager()
            agent._scope.load_from_file()
        if not args:
            ui.console.print(Text(agent._scope.format_display(), style="white"))
        elif args.startswith("add "):
            target = args[4:].strip()
            agent._scope.add_in_scope(target)
            ui.console.print(Text(f"  ✓ Added to scope: {target}", style="bold green"))
        elif args.startswith("exclude "):
            target = args[8:].strip()
            agent._scope.add_out_of_scope(target)
            ui.console.print(Text(f"  ✓ Excluded: {target}", style="bold red"))
        elif args.startswith("wildcard "):
            domain = args[9:].strip()
            agent._scope.add_wildcard(domain)
            ui.console.print(Text(f"  ✓ Wildcard added: *.{domain.lstrip('*.')}", style="bold green"))
        elif args == "save":
            agent._scope.save_to_file()
            ui.console.print(Text("  ✓ Scope saved to scope.json", style="bold green"))
        elif args == "load":
            if agent._scope.load_from_file():
                ui.console.print(Text("  ✓ Scope loaded from scope.json", style="bold green"))
            else:
                ui.console.print(Text("  ✗ No scope.json found", style="red"))
        elif args.startswith("check "):
            target = args[6:].strip()
            in_scope = agent._scope.is_in_scope(target)
            style = "bold green" if in_scope else "bold red"
            status = "IN SCOPE" if in_scope else "OUT OF SCOPE"
            ui.console.print(Text(f"  {target}: {status}", style=style))
        else:
            ui.console.print(Text("  Usage: /scope [add|exclude|wildcard|check|save|load] <target>", style="dim"))

    elif cmd == "/workflow" or cmd == "/wf":
        from zer0code.workflows import WorkflowRunner, WORKFLOWS
        if not args:
            table = Table(title="Bug Bounty Workflows", border_style="magenta")
            table.add_column("Name", style="bold magenta", width=20)
            table.add_column("Description", style="white")
            table.add_column("Steps", style="dim", width=6)
            for key, wf in WORKFLOWS.items():
                table.add_row(key, wf["description"][:50], str(len(wf["steps"])))
            ui.console.print(table)
            ui.console.print(Text("\n  /workflow <name> <target>  — e.g. /workflow full-recon target.com\n", style="dim"))
        else:
            parts = args.strip().split(maxsplit=1)
            wf_name = parts[0]
            target = parts[1] if len(parts) > 1 else ""
            if wf_name not in WORKFLOWS:
                ui.console.print(Text(f"  Unknown workflow: {wf_name}", style="red"))
            elif not target:
                wf = WORKFLOWS[wf_name]
                ui.console.print(Text(f"\n  {wf['name']}: {wf['description']}\n", style="bold magenta"))
                for i, step in enumerate(wf["steps"], 1):
                    ui.console.print(Text(f"  {i}. {step}", style="dim"))
                ui.console.print(Text(f"\n  /workflow {wf_name} <target> to run\n", style="dim"))
            else:
                if hasattr(agent, '_scope') and agent._scope.enabled and not agent._scope.is_in_scope(target):
                    ui.console.print(Text(f"  ✗ {target} is OUT OF SCOPE", style="bold red"))
                else:
                    runner = WorkflowRunner(agent=agent)
                    ui.console.print(Text(f"\n  Running: {WORKFLOWS[wf_name]['name']} on {target}\n", style="bold magenta"))
                    try:
                        result = await runner.run(wf_name, target)
                        ui.render_response(result)
                    except Exception as e:
                        ui.render_error(str(e))

    elif cmd == "/consolidate":
        if agent.memory_store:
            try:
                count = await agent.memory_store.consolidate_memories()
                ui.console.print(Text(f"  ✓ Consolidated {count} old memories", style="bold green"))
            except Exception as e:
                ui.console.print(Text(f"  Error: {e}", style="red"))
        else:
            ui.console.print(Text("  Memory not enabled.", style="dim"))

    elif cmd == "/bg":
        if not args:
            ui.console.print(Text("  Usage: /bg <prompt> — run task in background while you keep chatting", style="dim"))
        else:
            _bg_id = int(time.time()) % 10000
            async def _run_bg(task_id, prompt):
                collected = []
                try:
                    async for chunk in agent.run_stream(prompt):
                        if isinstance(chunk, str):
                            collected.append(chunk)
                except Exception as e:
                    ui.console.print(Text(f"\n  [bg:{task_id}] ✗ Error: {e}", style="red"))
                    return
                response = "".join(collected)
                if response:
                    ui.console.print(Text(f"\n  [bg:{task_id}] ✓ Complete:", style="bold green"))
                    ui.render_response(response)
                    ui.console.print(Text(f"  [bg:{task_id}] {agent.total_tokens:,} tokens · {agent.total_cost}", style="dim cyan"))
            task = asyncio.create_task(_run_bg(_bg_id, args))
            if not hasattr(agent, '_bg_tasks'):
                agent._bg_tasks = {}
            agent._bg_tasks[_bg_id] = {"task": task, "prompt": args[:50]}
            ui.console.print(Text(f"  ✓ Task #{_bg_id} started in background. Keep chatting.", style="bold green"))

    elif cmd == "/tasks":
        if hasattr(agent, '_bg_tasks') and agent._bg_tasks:
            for tid, info in list(agent._bg_tasks.items()):
                status = "running" if not info["task"].done() else "done"
                style = "bold yellow" if status == "running" else "bold green"
                ui.console.print(Text(f"  [{tid}] {status} — {info['prompt']}", style=style))
                if info["task"].done():
                    del agent._bg_tasks[tid]
        else:
            ui.console.print(Text("  No background tasks.", style="dim"))

    elif cmd == "/stop":
        if hasattr(agent, '_bg_tasks') and agent._bg_tasks:
            for tid, info in agent._bg_tasks.items():
                if not info["task"].done():
                    info["task"].cancel()
                    ui.console.print(Text(f"  ✗ Task #{tid} cancelled.", style="dim red"))
            agent._bg_tasks.clear()
        else:
            ui.console.print(Text("  No tasks to stop.", style="dim"))

    elif cmd == "/status":
        mem_count = 0
        if agent.memory_store:
            try:
                stats = await agent.memory_store.get_stats()
                mem_count = sum(stats.values())
            except Exception:
                pass
        ui.show_status(
            model=config.model,
            provider=config.provider,
            tokens=agent.total_tokens,
            memories=mem_count,
        )
        ui.console.print(Text(f"  Context: {agent.context_window_percent}% used", style="dim"))

    elif cmd == "/exit" or cmd == "/quit":
        return True

    else:
        ui.console.print(Text(f"  Unknown command: {cmd}. Type /help for commands.", style="yellow"))

    return False


async def interactive_session(config: ZeroCodeConfig, resume_session: str = "", print_mode: bool = False) -> None:
    try:
        from zer0code.credentials import CredentialManager
        cm = CredentialManager()
        for env_name in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"]:
            if not os.environ.get(env_name):
                saved = cm.get(env_name)
                if saved:
                    os.environ[env_name] = saved
    except Exception:
        pass

    ui = TerminalUI(
        config={"provider": config.provider, "model": config.model},
        theme_name=config.theme,
    )

    agent = ZeroCoreAgent(config)
    agent.brancher.current_messages = agent.conversation_history
    _spinner = [None]

    def _confirm_handler(prompt_text):
        if _spinner[0]:
            _spinner[0].stop()
        raise _PermissionPending(prompt_text)

    agent.permissions = PermissionManager(
        confirm_callback=_confirm_handler,
        auto_approve=False,
    )

    await agent.initialize()

    agent.register_tools(ALL_TOOLS)
    agent.register_tools(SECURITY_TOOLS)
    agent.register_tools(GIT_TOOLS)

    session_mgr = SessionManager()
    await session_mgr.init()
    agent.session_manager = session_mgr

    if resume_session:
        await agent.load_session(resume_session)
        ui.console.print(Text(f"  Resumed session: {resume_session}", style="bold green"))
    else:
        agent.session_id = await session_mgr.create_session(
            provider=config.provider,
            model=config.model,
        )

    diff_renderer = DiffRenderer()

    _last_file_path = [None]
    _tool_timer = [0.0]
    _task_start = [0.0]

    def _ts():
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")

    def on_tool_call(name, args):
        _tool_timer[0] = time.time()
        if _spinner[0]:
            _spinner[0].stop()
        ts = _ts()
        console.print(Text(f"  {ts}  ◐ Running {name}...", style="dim yellow"))
        ui.render_tool_call(name, args)
        if name == "read_file":
            _last_file_path[0] = args.get("file_path", "")

    def on_tool_result(name, result, hook_messages=None):
        elapsed = time.time() - _tool_timer[0] if _tool_timer[0] else 0
        ts = _ts()
        display = result.output if result.success else (result.error or "Error")
        if len(display) > 2000:
            display = display[:1000] + f"\n... ({len(display)} chars total) ...\n" + display[-500:]
        ui.render_tool_result(name, display, result.success)

        tl = Text()
        tl.append(f"  {ts} ", style="dim")
        tl.append(f"↳ ", style="dim")
        tl.append(f"{elapsed:.1f}s", style="dim green")
        tl.append(f" · {agent.total_tokens:,} tokens", style="dim cyan")
        tl.append(f" · {agent.total_cost}", style="dim cyan")
        tl.append(f" · ctx: {agent.context_window_percent}%", style="dim cyan")
        console.print(tl)

        if _spinner[0]:
            _spinner[0].update(f"[bold green]  Analyzing results...")
            _spinner[0].start()

        if name == "read_file" and result.success and _last_file_path[0]:
            fp = _last_file_path[0]
            if fp.endswith((".html", ".htm")):
                import webbrowser
                abs_path = os.path.abspath(fp)
                webbrowser.open(f"file://{abs_path}")
                console.print(Text(f"  ↗ Opened in browser: {fp}", style="bold cyan"))

        if hook_messages:
            for msg in hook_messages:
                console.print(Text(f"  [lint] {msg}", style="dim"))

    agent.set_callbacks(on_tool_call=on_tool_call, on_tool_result=on_tool_result)

    console = ui.console
    width = console.width or 80

    console.print()
    logo = Text()
    logo.append("  ▄██▄  ", style="bold green")
    logo.append(f"ZER0CODE", style="bold green")
    logo.append(f" v{__version__}", style="dim")
    console.print(logo)

    line2 = Text()
    line2.append("  █  █  ", style="bold green")
    line2.append(f"{config.model}", style="bold cyan")
    line2.append(" · ", style="dim")
    line2.append(f"{config.provider.title()} API", style="dim")
    console.print(line2)

    line3 = Text()
    line3.append("  ▀██▀  ", style="bold green")
    line3.append(os.getcwd(), style="dim")
    console.print(line3)

    console.print()
    tools_count = len(agent.tool_registry)
    hint = Text()
    hint.append(f"   {tools_count} tools loaded", style="dim")
    hint.append(" · ", style="dim")
    hint.append("/switch", style="bold cyan")
    hint.append(" to change model", style="dim")
    console.print(hint)
    console.print()

    from prompt_toolkit.completion import WordCompleter
    slash_commands = WordCompleter([
        "/help", "/clear", "/memory", "/tools", "/config", "/model", "/provider",
        "/theme", "/compact", "/cost", "/session", "/skill", "/status", "/exit",
        "/persona", "/template", "/proxy", "/branch", "/export", "/undo", "/rollback",
        "/plugin", "/serve", "/budget", "/creds", "/lsp", "/quit",
        "/report", "/share", "/compare", "/update", "/cache", "/step",
        "/prompt", "/search", "/preview", "/env",
        "/init", "/doctor", "/login", "/approve", "/diff", "/turns", "/files", "/switch",
        "/scope", "/workflow", "/wf", "/consolidate", "/bg", "/tasks", "/stop",
    ], sentence=True)

    vi_mode = os.environ.get("ZER0CODE_VI_MODE", "").lower() in ("1", "true", "yes")

    session: PromptSession = PromptSession(
        history=FileHistory(str(get_history_path())),
        auto_suggest=AutoSuggestFromHistory(),
        completer=slash_commands,
        vi_mode=vi_mode,
    )

    agent._switch_pending = None
    agent._permission_pending = None

    while True:
        try:
            pending = getattr(agent, '_switch_pending', None)
            perm = getattr(agent, '_permission_pending', None)
            if perm:
                ptxt = "approve (y/n) ❯ "
            elif pending:
                if pending["step"] == "select_provider":
                    ptxt = "select ❯ "
                elif pending["step"] == "enter_key":
                    ptxt = "key ❯ "
                elif pending["step"] == "select_model":
                    ptxt = "model ❯ "
                else:
                    ptxt = "❯ "
            else:
                ptxt = "❯ "

            console.print(Text("─" * width, style="dim"))
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda pt=ptxt: session.prompt(
                    [("class:prompt", pt)],
                    style=None,
                ),
            )
            console.print(Text("─" * width, style="dim"))

            if not user_input or not user_input.strip():
                if agent._switch_pending:
                    agent._switch_pending = None
                    console.print(Text("  Cancelled.", style="dim"))
                if agent._permission_pending:
                    agent._permission_pending = None
                    console.print(Text("  ✗ Denied.", style="dim red"))
                continue

            user_input = user_input.strip()

            if agent._permission_pending:
                pp = agent._permission_pending
                if user_input.lower() in ("y", "yes"):
                    console.print(Text("  ✓ Approved", style="bold green"))
                    agent.permissions.auto_approve = True
                    agent._permission_pending = None
                    user_input = pp["user_input"]
                else:
                    console.print(Text("  ✗ Denied — tool skipped.", style="dim red"))
                    agent._permission_pending = None
                    continue

            if agent._switch_pending:
                sp = agent._switch_pending
                if sp["step"] == "select_provider":
                    provs = sp["providers"]
                    _PM = sp["pm"]
                    _EK = sp["ek"]
                    sel = None
                    if user_input.isdigit() and 1 <= int(user_input) <= len(provs):
                        sel = provs[int(user_input) - 1]
                    elif user_input.lower() in VALID_PROVIDERS:
                        sel = user_input.lower()
                    if not sel:
                        agent._switch_pending = None
                        console.print(Text("  Cancelled.", style="dim"))
                        continue
                    ek = _EK.get(sel)
                    if ek and not os.environ.get(ek):
                        console.print(Text(f"\n  ✗ {ek} not set. Type your API key (Enter to cancel):\n", style="bold red"))
                        agent._switch_pending = {"step": "enter_key", "provider": sel, "env_key": ek, "model": None, "pm": _PM}
                    else:
                        models = _PM.get(sel, [])
                        console.print(Text(f"\n  Models for {sel}:\n", style="bold cyan"))
                        for i, m in enumerate(models, 1):
                            mk = " ◀" if m == config.model else ""
                            ln = Text()
                            ln.append(f"  [{i}] ", style="bold cyan")
                            ln.append(m, style="bold white")
                            ln.append(mk, style="bold green")
                            console.print(ln)
                        console.print(Text(f"\n  Type number (Enter for default):\n", style="dim"))
                        agent._switch_pending = {"step": "select_model", "provider": sel, "models": models}
                    continue

                elif sp["step"] == "enter_key":
                    os.environ[sp["env_key"]] = user_input
                    try:
                        from zer0code.credentials import CredentialManager
                        CredentialManager().set(sp["env_key"], user_input)
                    except Exception:
                        pass
                    console.print(Text("  ✓ API key saved.", style="bold green"))
                    prov = sp["provider"]
                    if sp.get("model"):
                        config.provider = prov
                        config.model = sp["model"]
                        config.save()
                        await agent.initialize()
                        console.print(Text(f"  ✓ Switched to: {config.provider}/{config.model}", style="bold green"))
                        agent._switch_pending = None
                    else:
                        models = sp["pm"].get(prov, [])
                        console.print(Text(f"\n  Models for {prov}:\n", style="bold cyan"))
                        for i, m in enumerate(models, 1):
                            ln = Text()
                            ln.append(f"  [{i}] ", style="bold cyan")
                            ln.append(m, style="bold white")
                            console.print(ln)
                        console.print(Text(f"\n  Type number (Enter for default):\n", style="dim"))
                        agent._switch_pending = {"step": "select_model", "provider": prov, "models": models}
                    continue

                elif sp["step"] == "select_model":
                    models = sp["models"]
                    if user_input.isdigit() and 1 <= int(user_input) <= len(models):
                        sel_model = models[int(user_input) - 1]
                    else:
                        sel_model = models[0] if models else config.model
                    config.provider = sp["provider"]
                    config.model = sel_model
                    config.save()
                    await agent.initialize()
                    console.print(Text(f"\n  ✓ Switched to: {config.provider}/{config.model}\n", style="bold green"))
                    agent._switch_pending = None
                    continue

            if not user_input or not user_input.strip():
                continue

            user_input = user_input.strip()

            if user_input.startswith("/"):
                should_exit = await handle_slash_command(user_input, agent, config, ui, session_mgr)
                if should_exit:
                    ui.console.print(Text("\n  Session terminated. Stay sharp.\n", style="bold green"))
                    break
                continue

            console.print()
            _task_start[0] = time.time()
            history_len = len(agent.conversation_history)
            console.print(Text("  Ctrl+C to cancel", style="dim"), end="")
            console.print()

            collected_text = []
            got_text = False
            try:
                with console.status("[bold green]  Thinking...", spinner="dots", spinner_style="green") as status:
                    _spinner[0] = status
                    async for chunk in agent.run_stream(user_input):
                        if isinstance(chunk, str):
                            if not got_text:
                                status.update("[bold green]  Generating response...")
                                got_text = True
                            collected_text.append(chunk)
                    _spinner[0] = None
            except _PermissionPending as pp:
                _spinner[0] = None
                agent.conversation_history = agent.conversation_history[:history_len]
                console.print()
                console.print(Text(f"  ? {pp.description}", style="bold yellow"))
                console.print(Text(f"\n  Type 'y' to approve, 'n' to deny:\n", style="dim"))
                agent._permission_pending = {"description": pp.description, "user_input": user_input}
                continue
            except Exception as e:
                _spinner[0] = None
                agent.conversation_history = agent.conversation_history[:history_len]
                ui.render_error(str(e))
                continue

            task_elapsed = time.time() - _task_start[0]

            response = "".join(collected_text)
            if response:
                console.print(Text(f"  {_ts()}  ✓ Done ({task_elapsed:.1f}s)", style="dim green"))
                ui.render_response(response)
                if agent.reflection:
                    try:
                        conf = agent.reflection.assess_confidence_detailed(agent.conversation_history)
                        conf_style = "bold green" if conf["level"] == "HIGH" else "bold yellow" if conf["level"] == "MEDIUM" else "bold red"
                        console.print(Text(f"  confidence: {conf['level']} ({conf['score']}%) — {conf['detail']}", style=conf_style))
                    except Exception:
                        pass

            persona = getattr(config, 'persona', 'default')
            status_line = Text()
            status_line.append(f"  [{persona}]", style="bold magenta")
            right = f"{agent.total_tokens:,} tokens · {agent.total_cost} · ctx: {agent.context_window_percent}% · {task_elapsed:.1f}s"
            padding = width - len(f"  [{persona}]") - len(right) - 2
            status_line.append(" " * max(padding, 2))
            status_line.append(f"{agent.total_tokens:,} tokens", style="dim")
            status_line.append(" · ", style="dim")
            status_line.append(f"{agent.total_cost}", style="dim")
            status_line.append(" · ", style="dim")
            pct = agent.context_window_percent
            pct_style = "dim red" if pct > 80 else "dim yellow" if pct > 50 else "dim"
            status_line.append(f"ctx: {pct}%", style=pct_style)
            status_line.append(" · ", style="dim")
            status_line.append(f"{task_elapsed:.1f}s", style="dim green")
            console.print(status_line)
            agent.permissions.auto_approve = False
            import sys
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                import termios
                termios.tcflush(sys.stdin, termios.TCIFLUSH)
            except Exception:
                pass

        except KeyboardInterrupt:
            agent._switch_pending = None
            agent._permission_pending = None
            console.print(Text("\n\n  Session terminated. Stay sharp.\n", style="bold green"))
            break

        except EOFError:
            console.print(Text("\n\n  Session terminated. Stay sharp.\n", style="bold green"))
            break

        except Exception as e:
            ui.render_error(f"Unexpected error: {e}")
            continue

    if session_mgr:
        await session_mgr.close()
    if agent.memory_store and hasattr(agent.memory_store, '_db') and agent.memory_store._db:
        try:
            await agent.memory_store._db.close()
        except Exception:
            pass
    os._exit(0)


def _launch_tui_sync(config: ZeroCodeConfig, resume: str = "") -> None:
    from zer0code.tui_app import run_tui, HAS_TEXTUAL
    if not HAS_TEXTUAL:
        print("TUI mode requires 'textual'. Install: pip install zer0code[tui]")
        print("Falling back to REPL mode...")
        asyncio.run(interactive_session(config, resume_session=resume))
        return

    async def _init_agent():
        agent = ZeroCoreAgent(config)
        await agent.initialize()
        agent.register_tools(ALL_TOOLS)
        agent.register_tools(SECURITY_TOOLS)
        agent.register_tools(GIT_TOOLS)
        session_mgr = SessionManager()
        await session_mgr.init()
        agent.session_manager = session_mgr
        if resume:
            await agent.load_session(resume)
        else:
            agent.session_id = await session_mgr.create_session(provider=config.provider, model=config.model)
        return agent

    agent = asyncio.run(_init_agent())
    run_tui(agent=agent, config=config)


@click.group(invoke_without_command=True)
@click.option("--provider", "-p", default=None, help="LLM provider")
@click.option("--model", "-m", default=None, help="Model name")
@click.option("--resume", "-r", default="", help="Resume session ID")
@click.option("--continue-last", "-c", is_flag=True, default=False, help="Continue most recent session")
@click.option("--print-mode", is_flag=True, default=False, help="Non-interactive mode, print output and exit")
@click.option("--tui", is_flag=True, default=False, help="Launch full-screen TUI mode (Ctrl+B panels, Textual app)")
@click.option("--theme", "-t", default=None, help="UI theme")
@click.pass_context
def cli(ctx: click.Context, provider: str, model: str, resume: str, continue_last: bool, print_mode: bool, tui: bool, theme: str) -> None:
    ctx.ensure_object(dict)
    config = ZeroCodeConfig.load()
    if provider:
        config.provider = provider
    if model:
        config.model = model
    if theme:
        config.theme = theme
    ctx.obj["config"] = config

    if continue_last:
        import asyncio as _aio
        async def _get_last():
            mgr = SessionManager()
            await mgr.init()
            sessions = await mgr.list_sessions(limit=1)
            await mgr.close()
            return sessions[0].session_id if sessions else ""
        try:
            resume = _aio.run(_get_last())
        except Exception:
            pass

    if ctx.invoked_subcommand is None:
        if tui:
            _launch_tui_sync(config, resume)
        else:
            asyncio.run(interactive_session(config, resume_session=resume, print_mode=print_mode))


@cli.command()
@click.argument("prompt")
@click.pass_context
def run(ctx: click.Context, prompt: str) -> None:
    config = ctx.obj["config"]
    console = Console()

    async def _run() -> None:
        agent = ZeroCoreAgent(config)
        await agent.initialize()
        agent.register_tools(ALL_TOOLS)
        agent.register_tools(SECURITY_TOOLS)
        agent.register_tools(GIT_TOOLS)
        response = await agent.run(prompt)
        console.print(Markdown(response))
        console.print(Text(f"\n  Tokens: {agent.total_tokens:,} | Cost: {agent.total_cost}", style="dim"))

    asyncio.run(_run())


@cli.command()
@click.pass_context
def config(ctx: click.Context) -> None:
    cfg = ctx.obj["config"]
    console = Console()
    table = Table(title="ZER0CODE Configuration", border_style="cyan")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="white")
    table.add_row("Provider", cfg.provider)
    table.add_row("Model", cfg.model)
    table.add_row("API Key", "***set***" if cfg.api_key else "not set")
    table.add_row("Ollama URL", cfg.ollama_base_url)
    table.add_row("Memory Enabled", str(cfg.memory_enabled))
    table.add_row("Memory DB", cfg.memory_db_path)
    table.add_row("Max Tokens", str(cfg.max_context_tokens))
    table.add_row("Theme", cfg.theme)
    table.add_row("Wordlists", cfg.security_tools.wordlists_path)
    table.add_row("Proxy", f"{cfg.security_tools.proxy_host}:{cfg.security_tools.proxy_port}" if cfg.security_tools.use_proxy else "disabled")
    console.print(table)
    console.print(Text(f"\n  Config file: {CONFIG_DIR / 'config.json'}", style="dim"))


@cli.command()
@click.pass_context
def sessions(ctx: click.Context) -> None:
    console = Console()

    async def _list():
        mgr = SessionManager()
        await mgr.init()
        session_list = await mgr.list_sessions()
        if session_list:
            table = Table(title="Sessions", border_style="cyan")
            table.add_column("ID", style="bold cyan")
            table.add_column("Title")
            table.add_column("Messages", style="dim")
            table.add_column("Updated", style="dim")
            table.add_column("Model", style="dim")
            for s in session_list:
                updated = datetime.fromtimestamp(s.updated_at).strftime("%Y-%m-%d %H:%M")
                table.add_row(s.session_id, s.title, str(s.message_count), updated, s.model)
            console.print(table)
        else:
            console.print(Text("  No sessions found.", style="dim"))
        await mgr.close()

    asyncio.run(_list())


@cli.command()
@click.pass_context
def memory(ctx: click.Context) -> None:
    console = Console()

    async def _show():
        from zer0code.memory import MemoryStore
        store = MemoryStore()
        await store.init()
        stats = await store.get_stats()
        all_mem = await store.get_all_memories(limit=30)

        table = Table(title="Memory Store", border_style="green")
        table.add_column("Type", style="bold")
        table.add_column("Count", style="cyan")
        for k, v in stats.items():
            table.add_row(k, str(v))
        console.print(table)

        if all_mem.get("mistakes"):
            console.print(Text("\n  Recent Mistakes:", style="bold red"))
            for m in all_mem["mistakes"][:5]:
                console.print(Text(f"    - {m.get('lesson', '')[:100]}", style="dim"))

        if all_mem.get("successes"):
            console.print(Text("\n  Recent Successes:", style="bold green"))
            for s in all_mem["successes"][:5]:
                console.print(Text(f"    - {s.get('approach', '')[:100]}", style="dim"))

    asyncio.run(_show())


@cli.command()
def version() -> None:
    Console().print(
        f"\n  [bold green]{__codename__}[/] v{__version__}\n"
        f"  Autonomous AI Coding Agent for Penetration Testers\n"
    )


@cli.command()
@click.pass_context
def tui(ctx: click.Context) -> None:
    config = ctx.obj["config"]
    _launch_tui_sync(config)


def main() -> None:
    cli(obj={})
