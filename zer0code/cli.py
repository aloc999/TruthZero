import asyncio
import sys
from pathlib import Path

import click
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from zer0code import __codename__, __version__
from zer0code.agent import ZeroCoreAgent
from zer0code.config import CONFIG_DIR, ZeroCodeConfig

CUSTOM_THEME = Theme(
    {
        "banner": "bold green",
        "prompt": "bold cyan",
        "info": "dim white",
        "warning": "bold yellow",
        "error": "bold red",
        "success": "bold green",
        "tool": "bold magenta",
    }
)

console = Console(theme=CUSTOM_THEME)

BANNER = r"""
 _______ ____  ___   ____ ___  ____  _____
|__  / __| _ \/ _ \ / ___/ _ \|  _ \| ____|
  / /|  _|  _/ | | | |  | | | | | | |  _|
 / /_| |_| | | |_| | |__| |_| | |_| | |___
/____|___|_|  \___/ \____\___/|____/|_____|
"""

HELP_TEXT = """
[bold cyan]Slash Commands:[/]
  [green]/help[/]      Show this help message
  [green]/clear[/]     Clear conversation history
  [green]/memory[/]    Show learned memories
  [green]/tools[/]     List registered tools
  [green]/config[/]    Show current configuration
  [green]/model[/]     Switch model (usage: /model gpt-4o)
  [green]/provider[/]  Switch provider (usage: /provider anthropic)
  [green]/exit[/]      Exit ZER0CODE

[bold cyan]Keyboard Shortcuts:[/]
  [green]Ctrl+C[/]     Cancel current operation
  [green]Ctrl+D[/]     Exit ZER0CODE
"""


def get_history_path() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR / "history.txt"


async def handle_slash_command(
    command: str, agent: ZeroCoreAgent, config: ZeroCodeConfig
) -> bool:
    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "/help":
        console.print(HELP_TEXT)

    elif cmd == "/clear":
        agent.reset()
        console.print("[success]Conversation cleared.[/]")

    elif cmd == "/memory":
        if agent.memory:
            try:
                lessons = agent.memory.get_recent_lessons(limit=20)
                if lessons:
                    table = Table(title="Learned Memories", border_style="green")
                    table.add_column("#", style="dim")
                    table.add_column("Lesson", style="white")
                    for i, lesson in enumerate(lessons, 1):
                        table.add_row(str(i), str(lesson))
                    console.print(table)
                else:
                    console.print("[info]No memories stored yet.[/]")
            except Exception:
                console.print("[info]Memory system not initialized.[/]")
        else:
            console.print("[info]Memory system not enabled.[/]")

    elif cmd == "/tools":
        if agent.tool_registry:
            table = Table(title="Registered Tools", border_style="magenta")
            table.add_column("Tool", style="bold magenta")
            table.add_column("Description", style="white")
            for name, tool in agent.tool_registry.items():
                desc = getattr(tool, "description", "No description")
                table.add_row(name, desc)
            console.print(table)
        else:
            console.print("[info]No tools registered.[/]")

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
        table.add_row("Proxy", f"{config.security_tools.proxy_host}:{config.security_tools.proxy_port}" if config.security_tools.use_proxy else "disabled")
        table.add_row("Wordlists", config.security_tools.wordlists_path)
        console.print(table)

    elif cmd == "/model":
        if args:
            config.model = args.strip()
            config.save()
            console.print(f"[success]Model switched to: {config.model}[/]")
        else:
            console.print(f"[info]Current model: {config.model}[/]")
            console.print("[info]Usage: /model <model_name>[/]")

    elif cmd == "/provider":
        if args:
            provider = args.strip().lower()
            if provider in ("openai", "anthropic", "ollama"):
                config.provider = provider
                config.save()
                console.print(f"[success]Provider switched to: {config.provider}[/]")
            else:
                console.print("[error]Valid providers: openai, anthropic, ollama[/]")
        else:
            console.print(f"[info]Current provider: {config.provider}[/]")
            console.print("[info]Usage: /provider <openai|anthropic|ollama>[/]")

    elif cmd == "/exit":
        return True

    else:
        console.print(f"[warning]Unknown command: {cmd}[/]")
        console.print("[info]Type /help for available commands.[/]")

    return False


async def interactive_session(config: ZeroCodeConfig) -> None:
    agent = ZeroCoreAgent(config)

    console.print(Text(BANNER, style="banner"))
    console.print(
        Panel(
            f"[bold green]{__codename__}[/] v{__version__} | "
            f"Provider: [cyan]{config.provider}[/] | "
            f"Model: [cyan]{config.model}[/]\n"
            f"Type [bold]/help[/] for commands or start hacking.",
            border_style="green",
            title="[ OPERATIONAL ]",
            title_align="left",
        )
    )
    console.print()

    session: PromptSession = PromptSession(
        history=FileHistory(str(get_history_path())),
        auto_suggest=AutoSuggestFromHistory(),
    )

    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.prompt(
                    [("class:prompt", "zer0code"), ("", " > ")],
                    style=None,
                ),
            )

            if not user_input or not user_input.strip():
                continue

            user_input = user_input.strip()

            if user_input.startswith("/"):
                should_exit = await handle_slash_command(user_input, agent, config)
                if should_exit:
                    console.print("[success]Session terminated. Stay sharp.[/]")
                    break
                continue

            console.print()
            collected_response = []

            try:
                with Live(
                    Text("Thinking...", style="dim"),
                    console=console,
                    refresh_per_second=10,
                    transient=True,
                ):
                    response = await agent.run(user_input)
                    collected_response.append(response)
            except Exception as e:
                console.print(f"[error]Agent error: {e}[/]")
                continue

            if collected_response:
                full_response = "".join(collected_response)
                try:
                    console.print(Markdown(full_response))
                except Exception:
                    console.print(full_response)
            console.print()

        except KeyboardInterrupt:
            console.print("\n[warning]Operation cancelled.[/]")
            continue

        except EOFError:
            console.print("[success]Session terminated. Stay sharp.[/]")
            break

        except Exception as e:
            console.print(f"[error]Unexpected error: {e}[/]")
            continue


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)
    config = ZeroCodeConfig.load()
    ctx.obj["config"] = config

    if ctx.invoked_subcommand is None:
        asyncio.run(interactive_session(config))


@cli.command()
@click.argument("prompt")
@click.pass_context
def run(ctx: click.Context, prompt: str) -> None:
    config = ctx.obj["config"]

    async def _run() -> None:
        agent = ZeroCoreAgent(config)
        response = await agent.run(prompt)
        console.print(Markdown(response))

    asyncio.run(_run())


@cli.command()
@click.pass_context
def config(ctx: click.Context) -> None:
    cfg = ctx.obj["config"]
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
    table.add_row(
        "Proxy",
        f"{cfg.security_tools.proxy_host}:{cfg.security_tools.proxy_port}"
        if cfg.security_tools.use_proxy
        else "disabled",
    )
    console.print(table)
    console.print(f"\n[info]Config file: {CONFIG_DIR / 'config.json'}[/]")


@cli.command()
@click.pass_context
def memory(ctx: click.Context) -> None:
    console.print("[info]Memory system — no entries yet.[/]")


@cli.command()
def clear() -> None:
    console.print("[success]Conversation history cleared.[/]")


@cli.command()
def version() -> None:
    console.print(
        Panel(
            f"[bold green]{__codename__}[/] v{__version__}\n"
            f"Terminal-native AI agent for penetration testers.",
            border_style="green",
            title="[ VERSION ]",
        )
    )


def main() -> None:
    cli(obj={})
