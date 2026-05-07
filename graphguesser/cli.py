"""Click CLI — all game commands."""
import math
import os
import sys

import click
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .core import parse_function, compute_rmse, function_std, compute_score, evaluate_safe
from .hints import generate_hints
from .game import GameState, Team, load_game, save_game, GAME_FILE

console = Console()

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _plot_sample_points(state: GameState, path: str = "sample_points.png") -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    xs = [p[0] for p in state.sample_points]
    ys = [p[1] for p in state.sample_points]
    ax.scatter(xs, ys, color="royalblue", s=100, zorder=5, label="Sample points")
    for px, py in zip(xs, ys):
        ax.annotate(f"({px:.3g}, {py:.3g})", (px, py),
                    textcoords="offset points", xytext=(6, 6), fontsize=7)
    a, b = state.interval
    ax.set_xlim(a - 0.1 * (b - a), b + 0.1 * (b - a))
    ax.set_xlabel("x")
    ax.set_ylabel("f(x)")
    ax.set_title("GraphGuesser — Sample Points  (can you find f?)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def _plot_reveal(state: GameState, path: str = "reveal.png") -> None:
    a, b = state.interval
    xs = np.linspace(a, b, 600)
    fig, ax = plt.subplots(figsize=(10, 6))

    # True function
    try:
        f_true, _ = parse_function(state.function)
        yt = evaluate_safe(f_true, xs)
        ax.plot(xs, yt, "k-", linewidth=2.5, label=f"TRUE:  f(x) = {state.function}", zorder=10)
    except Exception:
        pass

    # Sample points
    spx = [p[0] for p in state.sample_points]
    spy = [p[1] for p in state.sample_points]
    ax.scatter(spx, spy, color="black", s=60, zorder=15, label="Sample points")

    # Team guesses
    colors = plt.cm.tab10.colors
    for i, team in enumerate(state.teams.values()):
        if not team.submission:
            continue
        try:
            f_guess, _ = parse_function(team.submission)
            yg = evaluate_safe(f_guess, xs)
            label = f"{team.name}:  {team.submission}  [score {team.score}]"
            ax.plot(xs, yg, "--", color=colors[i % len(colors)],
                    linewidth=1.8, label=label, alpha=0.85)
        except Exception:
            pass

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("GraphGuesser — Reveal")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def _leaderboard_table(state: GameState) -> Table:
    t = Table(title="LEADERBOARD", box=box.DOUBLE_EDGE, border_style="cyan")
    t.add_column("Rank", style="bold", justify="right")
    t.add_column("Team", style="cyan")
    t.add_column("Score", style="bold yellow", justify="right")
    t.add_column("RMSE", justify="right")
    t.add_column("Hints at submit", justify="center")
    t.add_column("Status")

    ranked = sorted(
        state.teams.values(),
        key=lambda tm: (-(tm.score or -1), tm.rmse or float("inf")),
    )
    for i, team in enumerate(ranked, 1):
        if team.score is not None:
            rmse_str  = f"{team.rmse:.5f}" if team.rmse is not None else "∞"
            hints_str = str(team.hints_at_submission)
            score_str = str(team.score)
            status    = "[green]Submitted[/green]"
        else:
            rmse_str = hints_str = score_str = "—"
            status = "[yellow]Pending[/yellow]"
        t.add_row(str(i), team.name, score_str, rmse_str, hints_str, status)
    return t


# ──────────────────────────────────────────────────────────────────────────────
# CLI group
# ──────────────────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """GraphGuesser — the mathematical function guessing game.\n
    \b
    Host commands:  setup · start · hint · scores · reveal
    Team command:   submit TEAM EXPRESSION
    """


# ──────────────────────────────────────────────────────────────────────────────
# setup
# ──────────────────────────────────────────────────────────────────────────────

@cli.command()
def setup():
    """Interactive setup wizard (run once before each round)."""
    console.print(Panel.fit("[bold cyan]GraphGuesser — Setup[/bold cyan]", border_style="cyan"))

    if os.path.exists(GAME_FILE):
        if not click.confirm(f"A game session already exists ({GAME_FILE}). Overwrite?"):
            console.print("Aborted.")
            sys.exit(0)

    # ── function ──────────────────────────────────────────────────────────────
    while True:
        func_str = click.prompt("\nEnter the mystery function  f(x)")
        try:
            f_true, expr = parse_function(func_str)
            console.print(f"  [green]✓ Parsed:[/green] f(x) = {expr}")
            break
        except ValueError as e:
            console.print(f"  [red]Error: {e}[/red]")

    # ── interval ─────────────────────────────────────────────────────────────
    a = click.prompt("Interval start  a", type=float)
    b = click.prompt("Interval end    b", type=float)
    if a >= b:
        console.print("[red]Error: a must be strictly less than b.[/red]")
        sys.exit(1)

    # ── sample points ─────────────────────────────────────────────────────────
    n_pts = click.prompt("Number of sample points", type=int, default=6)
    use_random = click.confirm("Use randomly placed sample points?", default=False)
    if use_random:
        raw_xs = np.sort(np.random.uniform(a, b, n_pts))
    else:
        raw_xs = np.linspace(a, b, n_pts)

    sample_points = [(float(px), float(f_true(px))) for px in raw_xs]

    console.print("\n[bold]Sample points:[/bold]")
    for px, py in sample_points:
        console.print(f"   x = {px:>10.5f}   →   f(x) = {py:.5f}")

    # ── scoring normalization ─────────────────────────────────────────────────
    f_std_val = function_std(f_true, a, b)

    # ── hints ─────────────────────────────────────────────────────────────────
    console.print("\n[bold]Generating hints…[/bold]")
    all_hints = generate_hints(expr, a, b)

    console.print(f"  Found {len(all_hints)} hints:\n")
    for i, h in enumerate(all_hints, 1):
        console.print(f"  [yellow]{i:2d}.[/yellow]  [{h['type']}]  {h['text']}")

    hint_order_str = click.prompt(
        "\nHint reveal order — enter numbers separated by spaces (or press Enter for default order)",
        default=" ".join(str(i) for i in range(1, len(all_hints) + 1)),
    )
    try:
        indices = [int(i) - 1 for i in hint_order_str.split()]
        selected_hints = [all_hints[i] for i in indices if 0 <= i < len(all_hints)]
        if not selected_hints:
            raise ValueError
    except (ValueError, IndexError):
        console.print("[yellow]Invalid selection — using all hints in default order.[/yellow]")
        selected_hints = all_hints

    hint_cost = click.prompt("Hint penalty (points per hint revealed)", type=int, default=50)

    # ── teams ─────────────────────────────────────────────────────────────────
    teams_input = click.prompt("\nTeam names (comma-separated)")
    team_names  = [t.strip() for t in teams_input.split(",") if t.strip()]
    if not team_names:
        console.print("[red]Need at least one team.[/red]")
        sys.exit(1)
    teams = {name: Team(name=name) for name in team_names}

    # ── save ─────────────────────────────────────────────────────────────────
    state = GameState(
        function=func_str,
        interval=(a, b),
        sample_points=sample_points,
        hints=selected_hints,
        hints_revealed=0,
        hint_cost=hint_cost,
        teams=teams,
        status="active",
        f_std=f_std_val,
    )
    save_game(state)
    _plot_sample_points(state)

    console.print(f"\n[bold green]✓ Game saved   →  {GAME_FILE}[/bold green]")
    console.print("[bold green]✓ Plot saved   →  sample_points.png[/bold green]")
    console.print("\nNext:  [cyan]python main.py start[/cyan]")


# ──────────────────────────────────────────────────────────────────────────────
# start
# ──────────────────────────────────────────────────────────────────────────────

@cli.command()
def start():
    """Display the sample points and game rules to all players."""
    state = load_game()
    a, b = state.interval

    console.print(Panel.fit("[bold cyan]GRAPHGUESSER — GAME ON[/bold cyan]", border_style="cyan"))
    console.print(f"  Interval :  [{a},  {b}]")
    console.print(f"  Teams    :  {',  '.join(state.teams)}")
    console.print(f"  Hints    :  {len(state.hints)} available  (each costs −{state.hint_cost} pts)\n")

    tbl = Table(title="Sample Points", box=box.SIMPLE_HEAD)
    tbl.add_column("x", style="cyan", justify="right")
    tbl.add_column("f(x)", style="yellow", justify="right")
    for px, py in state.sample_points:
        tbl.add_row(f"{px:.6f}", f"{py:.6f}")
    console.print(tbl)

    console.print("\n[dim]sample_points.png  ←  open this for the scatter plot[/dim]")
    console.print("\nCommands:  [cyan]hint[/cyan] · [cyan]hints[/cyan] · [cyan]submit TEAM EXPR[/cyan] · [cyan]scores[/cyan] · [cyan]reveal[/cyan]")


# ──────────────────────────────────────────────────────────────────────────────
# hint  (reveal next)
# ──────────────────────────────────────────────────────────────────────────────

@cli.command()
def hint():
    """Reveal the next hint (host command)."""
    state = load_game()

    if state.hints_revealed >= len(state.hints):
        console.print("[yellow]All hints have already been revealed.[/yellow]")
        return

    h = state.hints[state.hints_revealed]
    state.hints_revealed += 1
    save_game(state)

    console.print(Panel(
        f"[bold yellow]{h['text']}[/bold yellow]\n\n"
        f"[dim]Type: {h['type']}  ·  "
        f"Future submissions incur −{state.hint_cost} pts per hint revealed[/dim]",
        title=f"[bold]Hint {state.hints_revealed}  /  {len(state.hints)}[/bold]",
        border_style="yellow",
    ))


# ──────────────────────────────────────────────────────────────────────────────
# hints  (show all revealed so far)
# ──────────────────────────────────────────────────────────────────────────────

@cli.command()
def hints():
    """Show all hints that have been revealed so far."""
    state = load_game()

    if state.hints_revealed == 0:
        console.print("[yellow]No hints have been revealed yet.[/yellow]")
        return

    for i in range(state.hints_revealed):
        h = state.hints[i]
        console.print(f"[bold yellow]Hint {i + 1}[/bold yellow]  [{h['type']}]  {h['text']}")


# ──────────────────────────────────────────────────────────────────────────────
# submit
# ──────────────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("team_name")
@click.argument("expression")
def submit(team_name, expression):
    """Record TEAM_NAME's function guess EXPRESSION and compute their score.

    \b
    Examples:
      python main.py submit Alpha "2*x**3 - 3*x + 1"
      python main.py submit Beta  "sin(x) + x"
    """
    state = load_game()

    if state.status == "finished":
        console.print("[red]The game is already finished.[/red]")
        return

    if team_name not in state.teams:
        console.print(
            f"[red]Unknown team '{team_name}'.  Known teams: "
            + ", ".join(state.teams) + "[/red]"
        )
        return

    # Parse submission
    try:
        f_guess, expr_guess = parse_function(expression)
    except ValueError as e:
        console.print(f"[red]Cannot parse expression: {e}[/red]")
        return

    # Parse true function (host's)
    try:
        f_true, _ = parse_function(state.function)
    except ValueError as e:
        console.print(f"[red]Internal error reading true function: {e}[/red]")
        return

    a, b = state.interval
    rmse  = compute_rmse(f_true, f_guess, a, b)
    score = compute_score(rmse, state.f_std, state.hints_revealed, state.hint_cost)

    team = state.teams[team_name]
    team.submission         = expression
    team.hints_at_submission = state.hints_revealed
    team.rmse               = rmse if math.isfinite(rmse) else None
    team.score              = score
    save_game(state)

    norm  = rmse / max(state.f_std, 1e-10)
    acc   = round(1000 * math.exp(-2 * norm)) if math.isfinite(norm) else 0
    pen   = state.hints_revealed * state.hint_cost

    border = "green" if score >= 700 else ("yellow" if score >= 350 else "red")
    console.print(Panel(
        f"[bold]Team:[/bold]  {team_name}\n"
        f"[bold]Submission:[/bold]  f(x) = {expr_guess}\n"
        f"[bold]Hints revealed when submitted:[/bold]  {state.hints_revealed}\n"
        f"[bold]RMSE:[/bold]  {rmse:.6f}\n\n"
        f"  Accuracy score  :  {acc} / 1000\n"
        f"  Hint penalty    :  −{pen} pts\n"
        f"[bold]══ FINAL SCORE :  {score} pts ══[/bold]",
        title=f"Submission: {team_name}",
        border_style=border,
    ))

    if team.submission and team.submission != expression:
        console.print("[dim](Previous submission overwritten.)[/dim]")


# ──────────────────────────────────────────────────────────────────────────────
# scores
# ──────────────────────────────────────────────────────────────────────────────

@cli.command()
def scores():
    """Show the current leaderboard."""
    state = load_game()
    console.print(_leaderboard_table(state))
    console.print(
        f"\n[dim]Hints revealed: {state.hints_revealed} / {len(state.hints)}  "
        f"(−{state.hint_cost} pts each)[/dim]"
    )


# ──────────────────────────────────────────────────────────────────────────────
# reveal
# ──────────────────────────────────────────────────────────────────────────────

@cli.command()
def reveal():
    """End the game: show the true function and generate the reveal plot."""
    state = load_game()

    if not click.confirm("Reveal the answer and end the game?"):
        console.print("Aborted.")
        return

    state.status = "finished"
    save_game(state)

    console.print(Panel(
        f"[bold yellow]f(x)  =  {state.function}[/bold yellow]\n"
        f"[dim]on  [{state.interval[0]},  {state.interval[1]}][/dim]",
        title="[bold red]  THE ANSWER  [/bold red]",
        border_style="yellow",
    ))

    console.print()
    console.print(_leaderboard_table(state))

    _plot_reveal(state)
    console.print("\n[bold green]✓ reveal.png  generated — show it to everyone![/bold green]")
