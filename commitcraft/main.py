"""CommitCraft CLI entry point."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from . import __version__, config as config_mod, git_utils
from .providers import (
    AnthropicProvider,
    OllamaProvider,
    Provider,
    ProviderError,
)
from .providers.anthropic_api import DEFAULT_MODEL as ANTHROPIC_DEFAULT_MODEL
from .providers.ollama import DEFAULT_MODEL as OLLAMA_DEFAULT_MODEL


app = typer.Typer(
    name="cc",
    help="CommitCraft — AI commit messages. Fully offline. No API key needed.",
    no_args_is_help=False,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


PROVIDER_CHOICES = ("ollama", "anthropic")


# ---------- Provider selection ----------


def _build_provider(name: str, model: Optional[str]) -> Provider:
    if name == "ollama":
        return OllamaProvider(model=model)
    if name == "anthropic":
        return AnthropicProvider(model=model)
    raise typer.BadParameter(f"Unknown provider: {name}")


def _pick_provider(
    explicit: Optional[str], model: Optional[str]
) -> Optional[Provider]:
    """Resolve which provider to use based on CLI flag, config, and availability."""
    cfg = config_mod.load_config()

    # 1. Explicit flag wins.
    if explicit:
        return _build_provider(explicit, model)

    # 2. Config default if set.
    default = cfg.get("default_provider")
    if default in PROVIDER_CHOICES:
        chosen_model = model
        if not chosen_model:
            if default == "ollama":
                chosen_model = cfg.get("ollama_model")
            elif default == "anthropic":
                chosen_model = cfg.get("anthropic_model")
        return _build_provider(default, chosen_model)

    # 3. Auto-detect: prefer Ollama, else Anthropic.
    ollama = OllamaProvider(model=model or cfg.get("ollama_model"))
    if ollama.is_available():
        return ollama
    anthropic = AnthropicProvider(model=model or cfg.get("anthropic_model"))
    if anthropic.is_available():
        return anthropic
    return None


def _setup_help_panel() -> Panel:
    text = Text()
    text.append("No AI provider is available yet. Pick one:\n\n", style="bold")
    text.append("Option 1 — Offline via Ollama (free, private)\n", style="bold cyan")
    text.append("  1. Install Ollama:  https://ollama.com/download\n")
    text.append("  2. Start the server:  ")
    text.append("ollama serve\n", style="green")
    text.append("  3. Pull a model:  ")
    text.append(f"ollama pull {OLLAMA_DEFAULT_MODEL}\n\n", style="green")
    text.append("Option 2 — API via Anthropic (slightly better quality)\n", style="bold magenta")
    text.append("  1. Get a key at https://console.anthropic.com/\n")
    text.append("  2. Export it:  ")
    text.append("export ANTHROPIC_API_KEY=sk-ant-...\n\n", style="green")
    text.append("Then run  ")
    text.append("cc setup", style="bold green")
    text.append("  for an interactive wizard, or  ")
    text.append("cc doctor", style="bold green")
    text.append("  to diagnose.")
    return Panel(text, title="[bold]CommitCraft setup[/bold]", border_style="yellow")


# ---------- Default command: craft a commit ----------


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="Force a provider: ollama or anthropic.",
        case_sensitive=False,
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Override the model name for the chosen provider.",
    ),
    smart: bool = typer.Option(
        True,
        "--smart/--no-smart",
        help="Use the repo's last 20 commits as a style hint (default: on).",
    ),
    pr: bool = typer.Option(
        False,
        "--pr",
        help="Also generate a PR description in markdown after committing.",
    ),
) -> None:
    """Generate AI commit messages from your staged changes."""
    if ctx.invoked_subcommand is not None:
        return

    if provider and provider.lower() not in PROVIDER_CHOICES:
        raise typer.BadParameter(
            f"--provider must be one of: {', '.join(PROVIDER_CHOICES)}"
        )
    provider_name = provider.lower() if provider else None

    _craft_commit(provider_name=provider_name, model=model, smart=smart, want_pr=pr)


def _craft_commit(
    provider_name: Optional[str],
    model: Optional[str],
    smart: bool,
    want_pr: bool,
) -> None:
    # 1. Sanity: git repo?
    if not git_utils.is_git_repo():
        err_console.print(
            Panel(
                "Not a git repository. Run [bold]git init[/bold] first, "
                "or cd into an existing repo.",
                title="[red]Not a git repo[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    # 2. Staged changes?
    if not git_utils.has_staged_changes():
        console.print(
            Panel(
                "Nothing staged. Stage changes with [bold]git add <files>[/bold] and try again.",
                title="[yellow]Nothing to commit[/yellow]",
                border_style="yellow",
            )
        )
        raise typer.Exit(code=1)

    # 3. Show staged files.
    files = git_utils.get_staged_files()
    file_list = Text()
    for f in files[:10]:
        file_list.append(f"  • {f}\n")
    if len(files) > 10:
        file_list.append(f"  … and {len(files) - 10} more\n", style="dim")
    console.print(Panel(file_list, title=f"[bold]Staged ({len(files)} file{'s' if len(files) != 1 else ''})[/bold]", border_style="cyan"))

    # 4. Diff + truncate.
    try:
        diff = git_utils.get_staged_diff()
    except git_utils.GitError as exc:
        err_console.print(f"[red]Failed to read staged diff:[/red] {exc}")
        raise typer.Exit(code=1)
    diff = git_utils.truncate_diff(diff, max_chars=8000)

    # 5. Style hint from recent commits.
    style_hint: List[str] = []
    if smart:
        style_hint = git_utils.get_recent_commits(20)

    # 6. Pick provider.
    chosen = _pick_provider(provider_name, model)
    if chosen is None:
        console.print(_setup_help_panel())
        raise typer.Exit(code=1)

    # Validate availability early with a friendly error.
    if not chosen.is_available():
        if chosen.name == "ollama":
            err_console.print(
                Panel(
                    "Ollama doesn't appear to be running. Start it with:\n\n"
                    "  [green]ollama serve[/green]\n\n"
                    f"Then make sure the model is pulled:\n\n"
                    f"  [green]ollama pull {chosen.model}[/green]",
                    title="[red]Ollama not reachable[/red]",
                    border_style="red",
                )
            )
        else:
            err_console.print(
                Panel(
                    "ANTHROPIC_API_KEY is not set. Export it:\n\n"
                    "  [green]export ANTHROPIC_API_KEY=sk-ant-...[/green]\n\n"
                    "Or run [bold]cc setup[/bold] to configure.",
                    title="[red]Anthropic not configured[/red]",
                    border_style="red",
                )
            )
        raise typer.Exit(code=1)

    console.print(f"[dim]🤖 Using {chosen.name} ({chosen.model})[/dim]")

    # 7. Generate.
    try:
        with console.status("[cyan]Crafting commit messages…[/cyan]", spinner="dots"):
            result = chosen.generate_commits(diff, style_hint)
    except ProviderError as exc:
        err_console.print(
            Panel(str(exc), title="[red]Generation failed[/red]", border_style="red")
        )
        raise typer.Exit(code=1)

    suggestions = result.get("suggestions", [])
    if not suggestions:
        err_console.print("[red]Model returned no suggestions.[/red]")
        raise typer.Exit(code=1)

    _display_suggestions(suggestions, result)

    # 8. Interactive selection.
    choice = _prompt_choice(len(suggestions))
    if choice == "q":
        console.print("[dim]Aborted — nothing committed.[/dim]")
        raise typer.Exit(code=0)
    if choice == "r":
        console.print("[dim]Regenerating…[/dim]\n")
        return _craft_commit(provider_name, model, smart, want_pr)
    if choice == "e":
        picked = _edit_message(suggestions[0]["message"])
    else:
        idx = int(choice) - 1
        picked = suggestions[idx]["message"]

    if not picked or not picked.strip():
        err_console.print("[red]Empty commit message — aborted.[/red]")
        raise typer.Exit(code=1)

    ok, out = git_utils.commit_with_message(picked)
    if not ok:
        err_console.print(
            Panel(out or "git commit failed", title="[red]Commit failed[/red]", border_style="red")
        )
        raise typer.Exit(code=1)

    console.print(
        Panel(
            f"[green]✓ Committed:[/green] [bold]{picked}[/bold]",
            border_style="green",
        )
    )

    # 9. PR description (optional).
    if want_pr:
        try:
            with console.status("[cyan]Writing PR description…[/cyan]", spinner="dots"):
                pr_md = chosen.generate_pr(diff, [picked])
            console.print(Panel(pr_md, title="[bold]PR Description[/bold]", border_style="magenta"))
        except ProviderError as exc:
            err_console.print(f"[red]PR generation failed:[/red] {exc}")


def _display_suggestions(suggestions, result) -> None:
    table = Table(
        title="[bold]Commit suggestions[/bold]",
        show_lines=True,
        border_style="cyan",
        expand=True,
    )
    table.add_column("#", style="bold cyan", width=3, justify="center")
    table.add_column("Message", style="bold", overflow="fold")
    table.add_column("Why", style="dim", overflow="fold")
    for i, s in enumerate(suggestions[:3], start=1):
        msg = str(s.get("message", "")).strip()
        why = str(s.get("reasoning", "")).strip()
        table.add_row(str(i), msg, why)
    console.print(table)

    summary = str(result.get("summary", "") or "").strip()
    if summary:
        console.print(Panel(summary, title="[bold]Summary[/bold]", border_style="blue"))

    if result.get("breaking_change"):
        note = str(result.get("breaking_change_note", "") or "").strip() or "This change is breaking."
        console.print(
            Panel(
                f"⚠  {note}",
                title="[bold red]BREAKING CHANGE[/bold red]",
                border_style="red",
            )
        )


def _prompt_choice(n: int) -> str:
    valid = [str(i) for i in range(1, n + 1)] + ["e", "r", "q"]
    return Prompt.ask(
        "\n[bold]Pick[/bold] "
        + "/".join(str(i) for i in range(1, n + 1))
        + "  ·  [bold]e[/bold]dit  ·  [bold]r[/bold]egenerate  ·  [bold]q[/bold]uit",
        choices=valid,
        default="1",
        show_choices=False,
    )


def _edit_message(seed: str) -> str:
    """Open $EDITOR (or fall back to a prompt) so the user can tweak a message."""
    editor = os.environ.get("EDITOR") or shutil.which("nano") or shutil.which("vi")
    if not editor:
        return Prompt.ask("Edit message", default=seed)
    import tempfile

    with tempfile.NamedTemporaryFile("w+", suffix=".COMMIT_EDITMSG", delete=False) as tf:
        tf.write(seed + "\n")
        tf.flush()
        path = tf.name
    try:
        subprocess.call([editor, path])
        with open(path, "r", encoding="utf-8") as f:
            edited = f.read().strip()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return edited or seed


# ---------- Subcommands ----------


@app.command("version")
def version_cmd() -> None:
    """Show the installed version."""
    console.print(f"[bold cyan]CommitCraft[/bold cyan] v{__version__}")


@app.command("setup")
def setup_cmd() -> None:
    """Interactive setup wizard."""
    console.print(
        Panel(
            "Let's pick your default AI provider. You can change this later.",
            title="[bold]CommitCraft setup[/bold]",
            border_style="cyan",
        )
    )
    choice = Prompt.ask(
        "Which provider? [bold]o[/bold]llama (offline, free) · [bold]a[/bold]nthropic (API, cloud)",
        choices=["o", "a"],
        default="o",
    )
    cfg = config_mod.load_config()
    if choice == "o":
        ollama_model = Prompt.ask(
            "Ollama model",
            default=cfg.get("ollama_model") or OLLAMA_DEFAULT_MODEL,
        )
        cfg["default_provider"] = "ollama"
        cfg["ollama_model"] = ollama_model
        config_mod.save_config(cfg)
        probe = OllamaProvider(model=ollama_model)
        if probe.is_available():
            console.print("[green]✓[/green] Ollama is reachable.")
        else:
            console.print(
                "[yellow]![/yellow] Ollama isn't running yet. Start it with "
                "[green]ollama serve[/green] and pull the model with "
                f"[green]ollama pull {ollama_model}[/green]."
            )
    else:
        anthropic_model = Prompt.ask(
            "Anthropic model",
            default=cfg.get("anthropic_model") or ANTHROPIC_DEFAULT_MODEL,
        )
        cfg["default_provider"] = "anthropic"
        cfg["anthropic_model"] = anthropic_model
        config_mod.save_config(cfg)
        if os.environ.get("ANTHROPIC_API_KEY"):
            console.print("[green]✓[/green] ANTHROPIC_API_KEY detected.")
        else:
            console.print(
                "[yellow]![/yellow] ANTHROPIC_API_KEY not set. Export it in your shell:\n"
                "  [green]export ANTHROPIC_API_KEY=sk-ant-...[/green]"
            )
    console.print(
        f"\nSaved to [dim]{config_mod.CONFIG_PATH}[/dim]. "
        "Run [bold]cc[/bold] in a repo with staged changes to try it."
    )


@app.command("doctor")
def doctor_cmd() -> None:
    """Diagnose your CommitCraft setup."""
    console.print(Panel("[bold]CommitCraft diagnostic[/bold]", border_style="cyan"))

    # git
    git_ok = shutil.which("git") is not None
    _line(git_ok, "git on PATH", "Install git from https://git-scm.com/")

    # in a repo?
    in_repo = git_utils.is_git_repo()
    _line(
        in_repo,
        "Inside a git repository",
        "Run `git init` or cd into a repo (this check is informational).",
        warn_only=True,
    )

    # config
    cfg = config_mod.load_config()
    default = cfg.get("default_provider")
    if default:
        console.print(f"[green]✓[/green] Config default provider: [bold]{default}[/bold]")
    else:
        console.print("[yellow]•[/yellow] No default provider saved. Run [bold]cc setup[/bold].")

    # Ollama
    ollama = OllamaProvider(model=cfg.get("ollama_model"))
    ollama_ok = ollama.is_available()
    _line(
        ollama_ok,
        f"Ollama reachable at {ollama.host}",
        "Install from https://ollama.com and run `ollama serve`.",
        warn_only=True,
    )
    if ollama_ok:
        console.print(f"    model preference: [bold]{ollama.model}[/bold]")

    # Anthropic
    key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    _line(
        key_set,
        "ANTHROPIC_API_KEY env var set",
        "Export ANTHROPIC_API_KEY=sk-ant-... to enable API mode.",
        warn_only=True,
    )
    try:
        import anthropic  # noqa: F401

        console.print("[green]✓[/green] `anthropic` SDK installed")
    except ImportError:
        console.print(
            "[yellow]•[/yellow] `anthropic` SDK not installed "
            "(only needed for API mode): [green]pip install anthropic[/green]"
        )

    if ollama_ok or key_set:
        console.print("\n[bold green]You're good to go.[/bold green] Run [bold]cc[/bold] in a repo with staged changes.")
    else:
        console.print("\n[bold yellow]No provider is ready yet.[/bold yellow] Run [bold]cc setup[/bold].")


def _line(ok: bool, label: str, fix_hint: str, warn_only: bool = False) -> None:
    if ok:
        console.print(f"[green]✓[/green] {label}")
    else:
        marker = "[yellow]•[/yellow]" if warn_only else "[red]✗[/red]"
        console.print(f"{marker} {label}")
        console.print(f"    [dim]{fix_hint}[/dim]")


if __name__ == "__main__":
    app()
