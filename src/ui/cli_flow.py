"""
CLI Flow — Rich-based linear screens (Screens 1-4).

Handles the interactive pre-dashboard flow:
  Screen 1: ASCII art boot logo + User ID prompt
  Screen 2: Fast pre-check info box (user meta)
  Screen 2b: Cache update prompt (if flower count changed)
  Screen 3: Engine selection menu
  Screen 3b: AI cache prompt (if cached AI results exist)
  Screen 4: Heavy-lift progress display (scraping, embedding, LLM)
"""

import re
import textwrap
from datetime import datetime
from typing import Optional

import timeago
from bidi.algorithm import get_display
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)

console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def fix_bidi(text: str, width: int = 58) -> str:
    """
    Apply BiDi transformation line-by-line while also manually wrapping 
    to a visual width to prevent vertical row reversal in terminals.
    """
    if not text:
        return ""
    
    final_lines = []
    # Split by actual newlines first
    for logical_line in text.split("\n"):
        if not logical_line.strip():
            final_lines.append("")
            continue
            
        # Manually wrap the logical line into visual segments BEFORE BiDi
        segments = textwrap.wrap(
            logical_line, 
            width=width, 
            break_long_words=False, 
            replace_whitespace=False
        )
        # BiDi each visual segment and preserve their vertical top-down order
        for seg in segments:
            final_lines.append(get_display(seg))
            
    return "\n".join(final_lines)


# ---------------------------------------------------------------------------
# ASCII Art Logo
# ---------------------------------------------------------------------------
_LOGO = r"""
[bold cyan]
   _____ _______ _____ _____   _____
  / ____|__   __|_   _|  __ \ / ____|
 | (___    | |    | | | |__) | (___
  \___ \   | |    | | |  ___/ \___ \
  ____) |  | |   _| |_| |     ____) |
 |_____/   |_|  |_____|_|    |_____/

  [bold magenta]P R O F I L E R[/bold magenta]
[/bold cyan]
"""

_TAGLINE = "[dim]Psychological & Demographic Profiling via AI[/dim]"


# ===================================================================
# Screen 1: Boot Up
# ===================================================================
def screen_boot() -> str:
    """
    Display the boot screen with ASCII logo and prompt for a User ID.

    Returns the user ID as a string (could be a numeric ID or profile URL).
    """
    console.clear()
    console.print(_LOGO, justify="center")
    console.print(_TAGLINE, justify="center")
    console.print()

    raw_input = Prompt.ask(
        "[bold green]▶ Enter Stips User ID or Profile URL[/bold green]"
    )

    # Handle profile URLs like https://stips.co.il/profile/445444
    match = re.search(r"/profile/(\d+)", raw_input)
    if match:
        return match.group(1)

    # Strip non-numeric chars if they just pasted a number
    cleaned = raw_input.strip()
    if cleaned.isdigit():
        return cleaned

    # Return as-is, let the caller handle validation
    return cleaned


# ===================================================================
# Screen 2: Fast Pre-Check
# ===================================================================
def screen_precheck(
    user_id: int,
    nickname: str,
    flower_count: int,
    cached_count: int,
    age: Optional[int] = None,
) -> None:
    """Display the user info box after a fast metadata fetch."""
    # Estimate tokens: ~1.7 tokens/word for Hebrew, ~8 words per answer avg
    estimated_tokens = int(flower_count * 8 * 1.7)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold white", no_wrap=True)
    table.add_column(style="cyan")

    # Apply BiDi to the nickname!
    table.add_row("User Target:", f"@{fix_bidi(nickname)}")
    if age:
        table.add_row("Age:", str(age))
    table.add_row("Flowered Responses:", f"{flower_count:,}")
    if cached_count > 0:
        table.add_row("Cached Locally:", f"{cached_count:,}")
    table.add_row("Estimated Token Size:", f"~{estimated_tokens:,} tokens")

    panel = Panel(
        table,
        title="[bold yellow]🎯 Target Identified[/bold yellow]",
        border_style="yellow",
        padding=(1, 3),
    )
    console.print()
    console.print(panel)
    console.print()


# ===================================================================
# Screen 2b: Cache Update Prompt
# ===================================================================
def screen_cache_update_prompt(
    cached_flowers: int,
    current_flowers: int,
) -> bool:
    """
    If the flower count has changed since the last cache, ask the user
    whether to do an incremental update.

    Returns True if the user wants to update.
    """
    diff = current_flowers - cached_flowers
    direction = "more" if diff > 0 else "fewer"

    console.print(
        f"[bold yellow]⚠  Flower count changed![/bold yellow] "
        f"Cached: {cached_flowers:,} → Current: {current_flowers:,} "
        f"({abs(diff):,} {direction})"
    )
    return Confirm.ask(
        "[bold]Update cache with new responses?[/bold]",
        default=True,
    )


# ===================================================================
# Screen 3: Engine Selection
# ===================================================================
def screen_engine_selection(flower_count: int) -> str:
    """
    Display the engine selection menu with a dynamic recommendation.

    Returns "prompt_caching" or "embeddings".
    """
    recommended_idx = "1" if flower_count < 300 else "2"

    console.print("[bold green]▶ Select AI Processing Engine:[/bold green]")
    console.print()

    r1 = "[bold](Recommended)[/bold]" if recommended_idx == "1" else ""
    r2 = "[bold](Recommended)[/bold]" if recommended_idx == "2" else ""

    console.print(f"  [cyan]1.[/cyan] Prompt Caching + Few-Shot  {r1}")
    console.print(f"      [dim]Best for < 300 answers. Cheap, fast, parallel.[/dim]")
    console.print()
    console.print(f"  [cyan]2.[/cyan] Embeddings Vector Search + LLM  {r2}")
    console.print(f"      [dim]Best for > 300 answers. Semantic filtering, RAG.[/dim]")
    console.print()

    choice = Prompt.ask(
        "[bold]Enter choice[/bold]",
        choices=["1", "2"],
        default=recommended_idx,
    )
    return "prompt_caching" if choice == "1" else "embeddings"


# ===================================================================
# Screen 3b: AI Cache Prompt
# ===================================================================
def screen_ai_cache_prompt(engine_type: str, cached_at: float) -> bool:
    """
    If cached AI results exist, ask the user whether to load them or re-run.

    Args:
        engine_type: The engine type ("prompt_caching" or "embeddings").
        cached_at:   Unix timestamp of when the results were cached.

    Returns True if the user wants to use cached results, False to re-run.
    """
    engine_labels = {
        "prompt_caching": "Prompt Caching",
        "embeddings": "Embeddings + RAG",
    }
    label = engine_labels.get(engine_type, engine_type)

    now = datetime.now()
    cached_time = datetime.fromtimestamp(cached_at)
    time_ago = timeago.format(cached_time, now)

    console.print()
    console.print(
        f"[bold yellow]💾 Cached AI results found![/bold yellow] "
        f"Engine: [cyan]{label}[/cyan] — cached [green]{time_ago}[/green]"
    )

    return Confirm.ask(
        "[bold]Load cached results? (No = re-run AI analysis)[/bold]",
        default=True,
    )


# ===================================================================
# Screen 4: Progress Display
# ===================================================================
class ProgressDisplay:
    """
    Manages the animated progress display during the heavy-lift phase.
    Uses Rich's Live display with spinners and progress bars.
    """

    def __init__(self) -> None:
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        )
        self._tasks: dict[str, int] = {}

    def start(self) -> None:
        self._progress.start()

    def stop(self) -> None:
        self._progress.stop()

    def add_task(self, key: str, description: str, total: Optional[float] = None) -> None:
        task_id = self._progress.add_task(description, total=total)
        self._tasks[key] = task_id

    def update_task(
        self,
        key: str,
        advance: float = 0,
        completed: Optional[float] = None,
        description: Optional[str] = None,
    ) -> None:
        task_id = self._tasks.get(key)
        if task_id is None:
            return
        kwargs: dict = {}
        if advance:
            kwargs["advance"] = advance
        if completed is not None:
            kwargs["completed"] = completed
        if description is not None:
            kwargs["description"] = description
        self._progress.update(task_id, **kwargs)

    def complete_task(self, key: str, description: Optional[str] = None) -> None:
        task_id = self._tasks.get(key)
        if task_id is None:
            return
        task = self._progress.tasks[task_id]
        total = task.total or 1
        self._progress.update(
            task_id,
            completed=total,
            description=description or task.description,
        )


def screen_progress_cached(count: int) -> None:
    """Show a quick success message when loading from cache."""
    console.print(
        f"  [bold green]✓[/bold green] Loaded {count:,} responses from [cyan]Local Cache[/cyan]"
    )