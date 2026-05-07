"""
GraphGuesser GUI — host-operated graphical interface.
Run with:  python gui.py
"""
import math
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
from sympy import latex as sym_latex, sympify

from graphguesser.core import (
    parse_function, compute_rmse, function_std,
    compute_score, evaluate_safe,
)
from graphguesser.game import GameState, Team, save_game

# ══════════════════════════════  Palette  ════════════════════════════════════

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG_DARK   = "#0d1117"
BG_PANEL  = "#161b27"
BG_CARD   = "#1c2235"
ACCENT    = "#4f8ef7"
GOLD      = "#f9a825"
TEXT_MAIN = "#e8eaf6"
TEXT_DIM  = "#6b7a99"
SEP       = "#252c3f"
FIG_BG    = "#0d1021"
AX_BG     = "#111425"

TEAM_PALETTE = [
    "#4fc3f7", "#ef9a9a", "#a5d6a7", "#ffcc80",
    "#ce93d8", "#80cbc4", "#f48fb1", "#90caf9",
]
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _team_color(state: GameState, name: str) -> str:
    idx = list(state.teams.keys()).index(name)
    return TEAM_PALETTE[idx % len(TEAM_PALETTE)]


# ══════════════════════  LaTeX helpers  ══════════════════════════════════════

def to_latex(expr_str: str) -> str:
    """Convert an expression string to a LaTeX string via sympy."""
    try:
        return sym_latex(sympify(expr_str))
    except Exception:
        return expr_str.replace("**", "^").replace("*", r" \cdot ")


class LatexLabel(ctk.CTkFrame):
    """Embed a LaTeX-rendered math expression (via matplotlib mathtext)."""

    def __init__(self, parent, latex_str: str = "", fontsize: int = 15,
                 fg_color: str = BG_CARD, text_color: str = TEXT_MAIN,
                 fig_height: float = 0.55, **kwargs):
        super().__init__(parent, fg_color=fg_color, **kwargs)
        self._fontsize   = fontsize
        self._fg         = fg_color
        self._text_color = text_color

        self._fig = Figure(figsize=(6, fig_height), facecolor=fg_color)
        self._ax  = self._fig.add_axes([0, 0, 1, 1])
        self._ax.set_facecolor(fg_color)
        self._ax.axis("off")
        self._txt = self._ax.text(
            0.5, 0.5, "",
            transform=self._ax.transAxes,
            fontsize=fontsize, color=text_color,
            ha="center", va="center",
        )
        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)
        self._canvas.draw()

        if latex_str:
            self.set(latex_str)

    def set(self, latex_str: str) -> None:
        """Update the rendered expression. Pass a sympy latex string."""
        try:
            self._txt.set_text(f"${latex_str}$")
            self._txt.set_color(self._text_color)
        except Exception:
            self._txt.set_text(latex_str)
        self._canvas.draw_idle()

    def clear(self) -> None:
        self._txt.set_text("")
        self._canvas.draw_idle()


# ══════════════════════════  Plot helpers  ═══════════════════════════════════

def _styled_axes(ax):
    ax.set_facecolor(AX_BG)
    ax.grid(True, alpha=0.18, color="#2e3452")
    ax.tick_params(colors=TEXT_DIM, labelsize=8)
    for sp in ax.spines.values():
        sp.set_color(SEP)
    ax.xaxis.label.set_color(TEXT_MAIN)
    ax.yaxis.label.set_color(TEXT_MAIN)
    ax.title.set_color(TEXT_MAIN)


def _make_canvas(parent, figsize=(6, 4.5)):
    fig = Figure(figsize=figsize, facecolor=FIG_BG)
    ax  = fig.add_subplot(111)
    _styled_axes(ax)
    fig.tight_layout(pad=1.8)
    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.get_tk_widget().pack(fill="both", expand=True)
    return fig, ax, canvas


# ══════════════════════════════  App  ════════════════════════════════════════

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GraphGuesser")
        self.geometry("1400x860")
        self.minsize(1000, 680)
        self.configure(fg_color=BG_DARK)

        self._slot = ctk.CTkFrame(self, fg_color="transparent")
        self._slot.pack(fill="both", expand=True)
        self._current: ctk.CTkFrame | None = None

        self._show(SetupFrame(self._slot, self))

    def _show(self, frame: ctk.CTkFrame):
        if self._current:
            self._current.destroy()
        self._current = frame
        frame.pack(fill="both", expand=True)

    def go_game(self, state: GameState):
        save_game(state)
        self._show(GameFrame(self._slot, self, state))

    def go_results(self, state: GameState):
        state.status = "finished"
        save_game(state)
        self._show(ResultsFrame(self._slot, self, state))

    def go_setup(self):
        self._show(SetupFrame(self._slot, self))


# ══════════════════════════  SetupFrame  ═════════════════════════════════════

class SetupFrame(ctk.CTkFrame):
    def __init__(self, parent, app: App):
        super().__init__(parent, fg_color=BG_DARK)
        self._app = app
        self._team_names: list[str] = []
        self._build()

    def _build(self):
        # header
        hdr = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="◆  GraphGuesser",
                     font=("Helvetica", 22, "bold"), text_color=ACCENT).pack(side="left", padx=24)
        ctk.CTkLabel(hdr, text="New Game Setup",
                     font=("Helvetica", 14), text_color=TEXT_DIM).pack(side="left", padx=4)

        body = ctk.CTkScrollableFrame(self, fg_color=BG_DARK)
        body.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(body, fg_color="transparent")
        inner.pack(fill="x", padx=80, pady=20)
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=1)

        # ── left column ───────────────────────────────────────────────────
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self._card(left, "Mystery Function  f(x)")
        func_row = ctk.CTkFrame(left, fg_color="transparent")
        func_row.pack(fill="x", padx=16, pady=(0, 4))
        self._func_entry = ctk.CTkEntry(
            func_row, placeholder_text="e.g.  2*x**3 - 3*x + 1",
            font=("Courier", 13), height=40)
        self._func_entry.pack(side="left", fill="x", expand=True)
        self._func_entry.bind("<Return>", lambda _e: self._preview_func())
        ctk.CTkButton(func_row, text="Preview", width=80, height=40,
                      fg_color="#2a3550", hover_color="#1e2940",
                      command=self._preview_func).pack(side="left", padx=(6, 0))

        # LaTeX preview of the entered function
        preview_wrap = ctk.CTkFrame(left, fg_color=BG_CARD, corner_radius=8, height=62)
        preview_wrap.pack(fill="x", padx=16, pady=(0, 14))
        preview_wrap.pack_propagate(False)
        self._func_preview = LatexLabel(preview_wrap, fg_color=BG_CARD,
                                         text_color=GOLD, fontsize=16, fig_height=0.6)
        self._func_preview.pack(fill="both", expand=True)

        self._card(left, "Interval")
        ivl = ctk.CTkFrame(left, fg_color="transparent")
        ivl.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(ivl, text="a =", font=("Helvetica", 13)).pack(side="left")
        self._a_entry = ctk.CTkEntry(ivl, width=80, placeholder_text="-2")
        self._a_entry.pack(side="left", padx=8)
        ctk.CTkLabel(ivl, text="b =", font=("Helvetica", 13)).pack(side="left", padx=(16, 0))
        self._b_entry = ctk.CTkEntry(ivl, width=80, placeholder_text="2")
        self._b_entry.pack(side="left", padx=8)
        ctk.CTkFrame(left, fg_color="transparent", height=14).pack()

        self._card(left, "Sample Points")
        sp_row = ctk.CTkFrame(left, fg_color="transparent")
        sp_row.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(sp_row, text="Count:", font=("Helvetica", 13)).pack(side="left")
        self._n_var = tk.IntVar(value=6)
        ctk.CTkEntry(sp_row, textvariable=self._n_var, width=56).pack(side="left", padx=8)
        self._random_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(sp_row, text="Random spacing",
                        variable=self._random_var,
                        font=("Helvetica", 12)).pack(side="left", padx=20)

        # ── right column ──────────────────────────────────────────────────
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        self._card(right, "Teams")
        add_row = ctk.CTkFrame(right, fg_color="transparent")
        add_row.pack(fill="x", padx=16, pady=(0, 6))
        self._team_entry = ctk.CTkEntry(add_row, placeholder_text="Team name…", width=180)
        self._team_entry.pack(side="left")
        self._team_entry.bind("<Return>", lambda _e: self._add_team())
        ctk.CTkButton(add_row, text="+ Add", width=80,
                      command=self._add_team).pack(side="left", padx=8)

        self._teams_box = ctk.CTkFrame(right, fg_color="transparent")
        self._teams_box.pack(fill="x", padx=16, pady=(0, 14))

        for name in ("Alpha", "Beta", "Gamma"):
            self._add_team(name)

        # ── start button ──────────────────────────────────────────────────
        ctk.CTkButton(
            inner, text="▶  Start Game",
            height=54, font=("Helvetica", 17, "bold"),
            fg_color=ACCENT, hover_color="#3570d4",
            command=self._start,
        ).grid(row=1, column=0, columnspan=2, pady=24, sticky="ew")

    def _card(self, parent, title: str):
        ctk.CTkLabel(parent, text=title.upper(),
                     font=("Helvetica", 10, "bold"),
                     text_color=ACCENT).pack(anchor="w", padx=16, pady=(14, 3))

    def _preview_func(self):
        expr_str = self._func_entry.get().strip()
        if not expr_str:
            return
        try:
            parse_function(expr_str)          # validate
            self._func_preview.set(f"f(x) = {to_latex(expr_str)}")
        except ValueError as e:
            messagebox.showerror("Invalid function", str(e))

    def _add_team(self, name: str | None = None):
        if name is None:
            name = self._team_entry.get().strip()
            self._team_entry.delete(0, "end")
        if not name or name in self._team_names:
            return
        self._team_names.append(name)
        color = TEAM_PALETTE[len(self._team_names) % len(TEAM_PALETTE)]

        row = ctk.CTkFrame(self._teams_box, fg_color=BG_CARD, corner_radius=6)
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text="●", font=("Helvetica", 13),
                     text_color=color).pack(side="left", padx=(10, 4), pady=5)
        ctk.CTkLabel(row, text=name,
                     font=("Helvetica", 13)).pack(side="left", pady=5)
        ctk.CTkButton(row, text="✕", width=26, height=22,
                      fg_color="#2a2d3e", hover_color="#c0392b",
                      command=lambda n=name, r=row: self._remove_team(n, r),
                      ).pack(side="right", padx=8)

    def _remove_team(self, name: str, row: ctk.CTkFrame):
        if name in self._team_names:
            self._team_names.remove(name)
        row.destroy()

    def _start(self):
        func_str = self._func_entry.get().strip()
        if not func_str:
            messagebox.showerror("Missing input", "Enter the mystery function.")
            return
        try:
            f_true, _ = parse_function(func_str)
        except ValueError as e:
            messagebox.showerror("Invalid function", str(e))
            return

        a_str, b_str = self._a_entry.get().strip(), self._b_entry.get().strip()
        if not a_str or not b_str:
            messagebox.showerror("Missing input", "Enter both interval bounds.")
            return
        try:
            a, b = float(a_str), float(b_str)
        except ValueError:
            messagebox.showerror("Invalid interval", "Bounds must be numbers.")
            return
        if a >= b:
            messagebox.showerror("Invalid interval", "a must be strictly less than b.")
            return

        if not self._team_names:
            messagebox.showerror("No teams", "Add at least one team.")
            return

        n_pts = max(2, self._n_var.get())
        raw_xs = (np.sort(np.random.uniform(a, b, n_pts)) if self._random_var.get()
                  else np.linspace(a, b, n_pts))
        sample_points = [(float(px), float(f_true(px))) for px in raw_xs]

        state = GameState(
            function=func_str,
            interval=(a, b),
            sample_points=sample_points,
            hints=[],
            hints_revealed=0,
            hint_cost=0,
            teams={n: Team(name=n) for n in self._team_names},
            status="active",
            f_std=function_std(f_true, a, b),
        )
        self._app.go_game(state)


# ══════════════════════════  GameFrame  ══════════════════════════════════════

class GameFrame(ctk.CTkFrame):
    def __init__(self, parent, app: App, state: GameState):
        super().__init__(parent, fg_color=BG_DARK)
        self._app   = app
        self._state = state
        self._build()

    def _build(self):
        # top bar
        bar = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        a, b = self._state.interval
        ctk.CTkLabel(bar, text="◆  GraphGuesser",
                     font=("Helvetica", 20, "bold"), text_color=ACCENT).pack(side="left", padx=20)
        ctk.CTkLabel(bar, text=f"f(x) = ?   on  [{a}, {b}]",
                     font=("Courier", 13), text_color=TEXT_DIM).pack(side="left", padx=8)
        ctk.CTkButton(bar, text="End Game & Reveal  →", width=200,
                      height=36, font=("Helvetica", 13, "bold"),
                      fg_color=GOLD, hover_color="#c8860f", text_color="#0d0d0d",
                      command=self._end_game).pack(side="right", padx=20, pady=10)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2, minsize=380)
        body.grid_rowconfigure(0, weight=1)

        plot_panel = ctk.CTkFrame(body, fg_color=BG_PANEL, corner_radius=0)
        plot_panel.grid(row=0, column=0, sticky="nsew")

        ctrl_panel = ctk.CTkScrollableFrame(body, fg_color=BG_DARK, corner_radius=0,
                                             scrollbar_button_color=BG_PANEL)
        ctrl_panel.grid(row=0, column=1, sticky="nsew")

        self._build_plot(plot_panel)
        self._build_controls(ctrl_panel)

    # ── plot ──────────────────────────────────────────────────────────────────

    def _build_plot(self, parent):
        self._fig, self._ax, self._canvas = _make_canvas(parent)
        self._redraw_plot()

    def _redraw_plot(self):
        ax = self._ax
        ax.clear()
        _styled_axes(ax)
        ax.set_xlabel("x")
        ax.set_ylabel("f(x)")
        ax.set_title("Can you find  f(x)?", fontsize=12)

        xs = [p[0] for p in self._state.sample_points]
        ys = [p[1] for p in self._state.sample_points]
        ax.scatter(xs, ys, color="white", s=70, zorder=10, label="Sample points")

        a, b    = self._state.interval
        x_plot  = np.linspace(a, b, 500)
        for team in self._state.teams.values():
            if not team.submission:
                continue
            try:
                fg, _ = parse_function(team.submission)
                yg    = evaluate_safe(fg, x_plot)
                color = _team_color(self._state, team.name)
                try:
                    lt    = to_latex(team.submission)
                    label = rf"{team.name}:  $f = {lt}$"
                except Exception:
                    label = f"{team.name}:  {team.submission}"
                ax.plot(x_plot, yg, "--", color=color, linewidth=1.8,
                        alpha=0.85, label=label)
            except Exception:
                pass

        handles, labels = ax.get_legend_handles_labels()
        if labels:
            try:
                ax.legend(handles, labels, fontsize=7,
                          facecolor=BG_CARD, labelcolor=TEXT_MAIN, edgecolor=SEP)
            except Exception:
                ax.legend(handles, labels, fontsize=7)

        self._fig.tight_layout(pad=1.8)
        self._canvas.draw()

    # ── controls ──────────────────────────────────────────────────────────────

    def _build_controls(self, parent):
        self._section(parent, "SUBMIT A GUESS")

        sub_card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=8)
        sub_card.pack(fill="x", padx=14, pady=(0, 6))

        ctk.CTkLabel(sub_card, text="Team:", font=("Helvetica", 12)).pack(anchor="w", padx=12, pady=(12, 2))
        self._team_var = tk.StringVar(value=list(self._state.teams)[0])
        self._team_menu = ctk.CTkOptionMenu(sub_card, variable=self._team_var,
                                             values=list(self._state.teams))
        self._team_menu.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkLabel(sub_card, text="f(x) =", font=("Helvetica", 12)).pack(anchor="w", padx=12)
        self._expr_entry = ctk.CTkEntry(sub_card, placeholder_text="e.g.  x**2 + sin(x)",
                                         font=("Courier", 12))
        self._expr_entry.pack(fill="x", padx=12, pady=(2, 6))
        self._expr_entry.bind("<Return>", lambda _e: self._submit())

        ctk.CTkButton(sub_card, text="Submit", height=38,
                      fg_color=ACCENT, hover_color="#3570d4",
                      command=self._submit).pack(fill="x", padx=12, pady=(0, 8))

        # LaTeX render of the submitted expression
        ctk.CTkFrame(sub_card, height=1, fg_color=SEP).pack(fill="x", padx=12)
        self._status_lbl = ctk.CTkLabel(sub_card, text="",
                                         font=("Helvetica", 11), text_color=TEXT_DIM)
        self._status_lbl.pack(anchor="w", padx=12, pady=(6, 2))

        preview_wrap = ctk.CTkFrame(sub_card, fg_color=BG_PANEL, corner_radius=6, height=64)
        preview_wrap.pack(fill="x", padx=12, pady=(0, 12))
        preview_wrap.pack_propagate(False)
        self._submit_latex = LatexLabel(preview_wrap, fg_color=BG_PANEL,
                                         text_color=TEXT_MAIN, fontsize=15, fig_height=0.6)
        self._submit_latex.pack(fill="both", expand=True)

        self._sep(parent)

        # leaderboard
        self._section(parent, "LEADERBOARD")
        self._lb_card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=8)
        self._lb_card.pack(fill="x", padx=14, pady=(0, 20))
        self._refresh_leaderboard()

    def _section(self, parent, title: str):
        ctk.CTkLabel(parent, text=title, font=("Helvetica", 11, "bold"),
                     text_color=ACCENT).pack(anchor="w", padx=14, pady=(14, 4))

    def _sep(self, parent):
        ctk.CTkFrame(parent, height=1, fg_color=SEP).pack(fill="x", padx=14, pady=6)

    # ── actions ───────────────────────────────────────────────────────────────

    def _submit(self):
        s         = self._state
        team_name = self._team_var.get()
        expr_str  = self._expr_entry.get().strip()

        if not expr_str:
            self._status_lbl.configure(text="Enter an expression first.", text_color="#ff6b6b")
            return

        try:
            f_guess, _ = parse_function(expr_str)
        except ValueError as e:
            self._status_lbl.configure(text=f"Parse error: {e}", text_color="#ff6b6b")
            return

        try:
            f_true, _ = parse_function(s.function)
        except ValueError:
            return

        a, b  = s.interval
        rmse  = compute_rmse(f_true, f_guess, a, b)
        score = compute_score(rmse, s.f_std, 0, 0)

        team = s.teams[team_name]
        team.submission          = expr_str
        team.hints_at_submission = 0
        team.rmse                = rmse if math.isfinite(rmse) else None
        team.score               = score
        save_game(s)

        rmse_disp = f"{rmse:.5f}" if math.isfinite(rmse) else "∞"
        self._status_lbl.configure(
            text=f"✓  {team_name}  →  score {score}   RMSE {rmse_disp}",
            text_color="#69f0ae",
        )
        try:
            self._submit_latex.set(f"f(x) = {to_latex(expr_str)}")
        except Exception:
            self._submit_latex.clear()

        self._expr_entry.delete(0, "end")
        self._refresh_leaderboard()
        self._redraw_plot()

    def _refresh_leaderboard(self):
        for w in self._lb_card.winfo_children():
            w.destroy()

        ranked = sorted(
            self._state.teams.values(),
            key=lambda t: (-(t.score or -1), t.rmse or float("inf")),
        )
        for i, team in enumerate(ranked, 1):
            row = ctk.CTkFrame(self._lb_card, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=4)
            medal       = MEDALS.get(i, f"{i}.")
            color       = _team_color(self._state, team.name)
            score_str   = f"{team.score}" if team.score is not None else "—"
            score_color = "#69f0ae" if team.score is not None else TEXT_DIM
            ctk.CTkLabel(row, text=f"{medal}  {team.name}",
                         font=("Helvetica", 12, "bold"),
                         text_color=color).pack(side="left")
            ctk.CTkLabel(row, text=score_str,
                         font=("Helvetica", 12, "bold"),
                         text_color=score_color).pack(side="right")

    def _end_game(self):
        if not messagebox.askyesno("End Game", "Reveal the true function and show final results?"):
            return
        self._app.go_results(self._state)


# ══════════════════════════  ResultsFrame  ═══════════════════════════════════

class ResultsFrame(ctk.CTkFrame):
    def __init__(self, parent, app: App, state: GameState):
        super().__init__(parent, fg_color=BG_DARK)
        self._app   = app
        self._state = state
        self._build()

    def _build(self):
        bar = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="◆  GraphGuesser — Results",
                     font=("Helvetica", 20, "bold"), text_color=ACCENT).pack(side="left", padx=20)
        ctk.CTkButton(bar, text="New Game", width=130, height=36,
                      fg_color="#2d4f8a", hover_color="#1e3a6a",
                      command=self._app.go_setup).pack(side="right", padx=20, pady=10)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2, minsize=400)
        body.grid_rowconfigure(0, weight=1)

        plot_panel = ctk.CTkFrame(body, fg_color=BG_PANEL, corner_radius=0)
        plot_panel.grid(row=0, column=0, sticky="nsew")

        right = ctk.CTkScrollableFrame(body, fg_color=BG_DARK, corner_radius=0,
                                        scrollbar_button_color=BG_PANEL)
        right.grid(row=0, column=1, sticky="nsew")

        self._build_reveal_plot(plot_panel)
        self._build_right(right)

    # ── comparison plot ───────────────────────────────────────────────────────

    def _build_reveal_plot(self, parent):
        s      = self._state
        fig, ax, canvas = _make_canvas(parent)
        a, b   = s.interval
        x_plot = np.linspace(a, b, 600)

        # true function — white solid, LaTeX label
        try:
            f_true, _ = parse_function(s.function)
            yt = evaluate_safe(f_true, x_plot)
            try:
                true_label = rf"TRUE:  $f(x) = {to_latex(s.function)}$"
            except Exception:
                true_label = f"TRUE:  f(x) = {s.function}"
            ax.plot(x_plot, yt, color="white", linewidth=2.8, zorder=10, label=true_label)
        except Exception:
            f_true = None

        # sample points
        xs = [p[0] for p in s.sample_points]
        ys = [p[1] for p in s.sample_points]
        ax.scatter(xs, ys, color="white", s=60, zorder=15)

        # team guesses — colored dashed, LaTeX label, shaded error band
        for team in s.teams.values():
            if not team.submission:
                continue
            try:
                fg, _  = parse_function(team.submission)
                yg     = evaluate_safe(fg, x_plot)
                color  = _team_color(s, team.name)
                score_str = f"{team.score} pts" if team.score is not None else "—"
                try:
                    lt    = to_latex(team.submission)
                    label = rf"{team.name}:  $f = {lt}$  [{score_str}]"
                except Exception:
                    label = f"{team.name}:  {team.submission}  [{score_str}]"
                ax.plot(x_plot, yg, "--", color=color, linewidth=2.0, alpha=0.9, label=label)
                if f_true is not None:
                    try:
                        yt_arr = evaluate_safe(f_true, x_plot)
                        valid  = np.isfinite(yt_arr) & np.isfinite(yg)
                        ax.fill_between(x_plot, yt_arr, yg, where=valid, alpha=0.07, color=color)
                    except Exception:
                        pass
            except Exception:
                pass

        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_title("True function vs. team guesses", fontsize=12)
        try:
            ax.legend(fontsize=7, facecolor=BG_CARD, labelcolor=TEXT_MAIN, edgecolor=SEP)
        except Exception:
            ax.legend(fontsize=7)
        fig.tight_layout(pad=1.8)
        canvas.draw()

    # ── right panel ───────────────────────────────────────────────────────────

    def _build_right(self, parent):
        s = self._state

        # ── answer box ────────────────────────────────────────────────────
        ctk.CTkLabel(parent, text="THE ANSWER",
                     font=("Helvetica", 11, "bold"),
                     text_color=ACCENT).pack(anchor="w", padx=16, pady=(20, 4))

        ans_card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10)
        ans_card.pack(fill="x", padx=16, pady=(0, 16))

        # LaTeX render of the answer
        latex_wrap = ctk.CTkFrame(ans_card, fg_color=BG_CARD, corner_radius=0, height=80)
        latex_wrap.pack(fill="x", padx=12, pady=(12, 4))
        latex_wrap.pack_propagate(False)
        try:
            answer_latex = f"f(x) = {to_latex(s.function)}"
        except Exception:
            answer_latex = f"f(x) = {s.function}"
        LatexLabel(latex_wrap, latex_str=answer_latex, fontsize=18,
                   fg_color=BG_CARD, text_color=GOLD,
                   fig_height=0.75).pack(fill="both", expand=True)

        a, b = s.interval
        ctk.CTkLabel(ans_card, text=f"on  [{a},  {b}]",
                     font=("Helvetica", 12), text_color=TEXT_DIM).pack(padx=16, pady=(0, 12))

        # ── final leaderboard ─────────────────────────────────────────────
        ctk.CTkLabel(parent, text="FINAL LEADERBOARD",
                     font=("Helvetica", 11, "bold"),
                     text_color=ACCENT).pack(anchor="w", padx=16, pady=(0, 6))

        ranked = sorted(
            s.teams.values(),
            key=lambda t: (-(t.score or -1), t.rmse or float("inf")),
        )
        for i, team in enumerate(ranked, 1):
            color = _team_color(s, team.name)
            medal = MEDALS.get(i, f"{i}.")
            card  = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=8)
            card.pack(fill="x", padx=16, pady=4)

            # name + score row
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(10, 2))
            ctk.CTkLabel(top, text=f"{medal}  {team.name}",
                         font=("Helvetica", 14, "bold"), text_color=color).pack(side="left")
            score_str = f"{team.score} pts" if team.score is not None else "—"
            ctk.CTkLabel(top, text=score_str,
                         font=("Helvetica", 14, "bold"), text_color=TEXT_MAIN).pack(side="right")

            if team.submission:
                # LaTeX render of the submission
                sub_wrap = ctk.CTkFrame(card, fg_color=BG_PANEL, corner_radius=6, height=52)
                sub_wrap.pack(fill="x", padx=14, pady=(2, 4))
                sub_wrap.pack_propagate(False)
                try:
                    sub_latex = f"f(x) = {to_latex(team.submission)}"
                except Exception:
                    sub_latex = f"f(x) = {team.submission}"
                LatexLabel(sub_wrap, latex_str=sub_latex, fontsize=12,
                           fg_color=BG_PANEL, text_color=color,
                           fig_height=0.5).pack(fill="both", expand=True)

                rmse_str = f"{team.rmse:.5f}" if team.rmse is not None else "∞"
                ctk.CTkLabel(card, text=f"RMSE: {rmse_str}",
                             font=("Courier", 10), text_color=TEXT_DIM).pack(
                    anchor="w", padx=14, pady=(0, 10))
            else:
                ctk.CTkLabel(card, text="No submission",
                             font=("Helvetica", 11),
                             text_color="#e57373").pack(anchor="w", padx=14, pady=(0, 10))


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
