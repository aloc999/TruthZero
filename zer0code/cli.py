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
        if args:
            config.model = args.strip()
            config.save()
            await agent.initialize()
            ui.console.print(Text(f"  Model switched to: {config.model}", style="bold green"))
        else:
            ui.console.print(Text(f"  Current model: {config.model}", style="dim"))

    elif cmd == "/provider":
        if args:
            provider = args.strip().lower()
            if provider in VALID_PROVIDERS:
                config.provider = provider
                config.save()
                await agent.initialize()
                ui.console.print(Text(f"  Provider switched to: {config.provider}", style="bold green"))
            else:
                ui.console.print(Text(f"  Valid providers: {', '.join(VALID_PROVIDERS)}", style="red"))
        else:
            ui.console.print(Text(f"  Current provider: {config.provider} | Available: {', '.join(VALID_PROVIDERS)}", style="dim"))

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


async def interactive_session(config: ZeroCodeConfig, resume_session: str = "") -> None:
    ui = TerminalUI(
        config={"provider": config.provider, "model": config.model},
        theme_name=config.theme,
    )

    agent = ZeroCoreAgent(config)
    agent.brancher.current_messages = agent.conversation_history
    agent.permissions = PermissionManager(
        confirm_callback=ui.confirm,
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

    def on_tool_call(name, args):
        ui.render_tool_call(name, args)

    def on_tool_result(name, result, hook_messages=None):
        if name == "edit_file" and result.success:
            old_str = json.loads(result.output).get("old_string", "") if result.output.startswith("{") else ""
            new_str = json.loads(result.output).get("new_string", "") if result.output.startswith("{") else ""
        
        display = result.output if result.success else (result.error or "Error")
        if len(display) > 2000:
            display = display[:1000] + f"\n... ({len(display)} chars total) ...\n" + display[-500:]
        ui.render_tool_result(name, display, result.success)

        if hook_messages:
            for msg in hook_messages:
                ui.console.print(Text(f"  [lint] {msg}", style="dim"))

    agent.set_callbacks(on_tool_call=on_tool_call, on_tool_result=on_tool_result)

    ui.show_banner()
    ui.console.print(
        Text(f"  Session: {agent.session_id} | Type /help for commands\n", style="dim")
    )

    from prompt_toolkit.completion import WordCompleter
    slash_commands = WordCompleter([
        "/help", "/clear", "/memory", "/tools", "/config", "/model", "/provider",
        "/theme", "/compact", "/cost", "/session", "/skill", "/status", "/exit",
        "/persona", "/template", "/proxy", "/branch", "/export", "/undo", "/rollback",
        "/plugin", "/serve", "/budget", "/creds", "/lsp", "/quit",
        "/report", "/share", "/compare", "/update", "/cache", "/step",
        "/prompt", "/search", "/preview", "/env",
    ], sentence=True)

    session: PromptSession = PromptSession(
        history=FileHistory(str(get_history_path())),
        auto_suggest=AutoSuggestFromHistory(),
        completer=slash_commands,
    )

    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.prompt(
                    [("class:prompt", f"zer0code"), ("", " > ")],
                    style=None,
                ),
            )

            if not user_input or not user_input.strip():
                continue

            user_input = user_input.strip()

            if user_input.startswith("/"):
                should_exit = await handle_slash_command(user_input, agent, config, ui, session_mgr)
                if should_exit:
                    ui.console.print(Text("\n  Session terminated. Stay sharp.\n", style="bold green"))
                    break
                continue

            ui.console.print()

            try:
                response = await agent.run(user_input)
            except Exception as e:
                ui.render_error(str(e))
                continue

            if response:
                ui.render_response(response)

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

        except KeyboardInterrupt:
            ui.console.print(Text("\n  Operation cancelled.", style="yellow"))
            continue

        except EOFError:
            ui.console.print(Text("\n  Session terminated. Stay sharp.\n", style="bold green"))
            break

        except Exception as e:
            ui.render_error(f"Unexpected error: {e}")
            continue

    if session_mgr:
        await session_mgr.close()


@click.group(invoke_without_command=True)
@click.option("--provider", "-p", default=None, help="LLM provider")
@click.option("--model", "-m", default=None, help="Model name")
@click.option("--resume", "-r", default="", help="Resume session ID")
@click.option("--theme", "-t", default=None, help="UI theme")
@click.pass_context
def cli(ctx: click.Context, provider: str, model: str, resume: str, theme: str) -> None:
    ctx.ensure_object(dict)
    config = ZeroCodeConfig.load()
    if provider:
        config.provider = provider
    if model:
        config.model = model
    if theme:
        config.theme = theme
    ctx.obj["config"] = config

    if ctx.invoked_subcommand is None:
        asyncio.run(interactive_session(config, resume_session=resume))


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


def main() -> None:
    cli(obj={})
