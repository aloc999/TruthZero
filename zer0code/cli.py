import asyncio
import json
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
        from zer0code.skills import PENTESTING_SKILLS
        if args:
            skill_name = args.strip()
            if skill_name in PENTESTING_SKILLS:
                skill = PENTESTING_SKILLS[skill_name]
                agent.conversation_history.append({
                    "role": "system",
                    "content": f"LOADED SKILL: {skill['name']}\n{skill['system_prompt_addition']}",
                })
                ui.console.print(Text(f"  Skill loaded: {skill['name']}", style="bold green"))
                ui.console.print(Text(f"  {skill['description']}", style="dim"))
            else:
                ui.console.print(Text(f"  Unknown skill. Available: {', '.join(PENTESTING_SKILLS.keys())}", style="red"))
        else:
            table = Table(title="Pentesting Skills", border_style="magenta")
            table.add_column("Skill", style="bold magenta")
            table.add_column("Description", style="white")
            for name, skill in PENTESTING_SKILLS.items():
                table.add_row(name, skill["description"])
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

    session: PromptSession = PromptSession(
        history=FileHistory(str(get_history_path())),
        auto_suggest=AutoSuggestFromHistory(),
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
