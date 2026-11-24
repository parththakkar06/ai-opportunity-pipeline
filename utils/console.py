"""Rich terminal UI: per-agent spinners, token/cost lines, final summary."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from utils.costs import AgentTotals, CostTracker, fmt_cost

StatusFn = Callable[[str], None]


class PipelineUI:
    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def banner(self, business: str, provider: str, model: str, search: list[str], out_dir: Path) -> None:
        body = (
            f"[bold]{business}[/bold]\n"
            f"LLM: [cyan]{provider}[/cyan] · [cyan]{model}[/cyan]\n"
            f"Search chain: [cyan]{' → '.join(search)}[/cyan]\n"
            f"Output: [dim]{out_dir}[/dim]"
        )
        self.console.print(Panel(body, title="AI Opportunity Pipeline", border_style="magenta"))

    def stage_start(self, stage: int, title: str) -> None:
        self.console.rule(f"[bold magenta]Stage {stage}/4 · {title}")

    @contextmanager
    def agent(self, stage: int, title: str) -> Iterator[StatusFn]:
        label = f"[bold]{title}[/bold]"
        with self.console.status(f"{label} — starting…", spinner="dots") as status:
            def update(message: str) -> None:
                status.update(f"{label} — {message}")
            yield update

    def agent_done(self, title: str, elapsed: float, totals: AgentTotals, files: list[Path]) -> None:
        tokens = f"{totals.input_tokens:,} in / {totals.output_tokens:,} out"
        self.console.print(
            f"[green]✓[/green] {title} finished in {elapsed:.1f}s · {tokens} tokens · {fmt_cost(totals.cost_usd)}"
        )
        for f in files:
            self.console.print(f"   [dim]→ {f.name}[/dim]")

    def stage_done(self, stage: int, title: str, elapsed: float) -> None:
        """Hook for the API's progress stream; the CLI already printed per-agent lines."""

    def skipped(self, stage: int, title: str) -> None:
        self.console.print(f"[dim]↷ Stage {stage}/4 · {title} — reusing saved output[/dim]")

    def note(self, message: str) -> None:
        self.console.print(f"   [dim]{message}[/dim]")

    def warn(self, message: str) -> None:
        self.console.print(f"[yellow]⚠ {message}[/yellow]")

    def error(self, message: str) -> None:
        self.console.print(Panel(message, title="Pipeline failed", border_style="red"))

    def summary(self, out_dir: Path, files: list[Path], tracker: CostTracker, elapsed: float) -> None:
        table = Table(title="Deliverables", show_lines=False)
        table.add_column("File", style="cyan")
        table.add_column("Size", justify="right")
        for f in files:
            size = f.stat().st_size if f.exists() else 0
            table.add_row(f.name, f"{size / 1024:.1f} KB")
        self.console.print(table)

        cost = Table(title="Usage by agent")
        cost.add_column("Agent")
        cost.add_column("Calls", justify="right")
        cost.add_column("Input", justify="right")
        cost.add_column("Output", justify="right")
        cost.add_column("Cost", justify="right")
        for agent in dict.fromkeys(r.agent for r in tracker.records):
            t = tracker.for_agent(agent)
            cost.add_row(agent, str(t.calls), f"{t.input_tokens:,}", f"{t.output_tokens:,}", fmt_cost(t.cost_usd))
        total = tracker.total()
        cost.add_row("[bold]Total", str(total.calls), f"{total.input_tokens:,}", f"{total.output_tokens:,}",
                     f"[bold]{fmt_cost(total.cost_usd)}")
        self.console.print(cost)

        stages = sorted({r.stage for r in tracker.records if r.stage is not None})
        if stages:
            by_stage = Table(title="Tokens by stage")
            by_stage.add_column("Stage")
            by_stage.add_column("Calls", justify="right")
            by_stage.add_column("Input", justify="right")
            by_stage.add_column("Output", justify="right")
            for st in stages:
                t = tracker.for_stage(st)
                by_stage.add_row(str(st), str(t.calls), f"{t.input_tokens:,}", f"{t.output_tokens:,}")
            self.console.print(by_stage)

        prototype = out_dir / "04_prototype.html"
        extra = f"\nOpen the prototype: [cyan]open \"{prototype}\"[/cyan]" if prototype.exists() else ""
        self.console.print(Panel(
            f"All files saved to [bold]{out_dir}[/bold]\nTotal time {elapsed:.1f}s{extra}",
            title="Done", border_style="green",
        ))

