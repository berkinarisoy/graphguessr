"""GraphGuesser — Flask web application.

Run locally:   python app.py
Deploy:        Set ADMIN_PASSWORD and SECRET_KEY env vars, then push to Render/Railway.
"""
import json
import math
import os
import hashlib
from datetime import datetime
from functools import wraps

import numpy as np
from flask import (Flask, render_template, request, redirect,
                   url_for, session, jsonify, flash)

from graphguesser.core import (parse_function, compute_rmse,
                                function_std, compute_score)
from graphguesser.hints import generate_hints

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gg-dev-secret-changeme")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "mathclub")
WEB_GAME_FILE  = "web_game.json"


# ─────────────────────────────────────────────────────────────────────────────
# Game state helpers
# ─────────────────────────────────────────────────────────────────────────────

def _blank_game():
    return {
        "status": "setup",          # setup | active | finished
        "current_round": 0,
        "teams": [],
        "rounds": [],               # each round has its function hidden until revealed
        "submissions": {},          # round_idx -> team -> {expression, hints_when_submitted}
        "scores": {},               # round_idx -> team -> {rmse, accuracy, penalty, score}
    }


def load_game() -> dict:
    if not os.path.exists(WEB_GAME_FILE):
        return _blank_game()
    with open(WEB_GAME_FILE) as f:
        return json.load(f)


def save_game(game: dict):
    with open(WEB_GAME_FILE, "w") as f:
        json.dump(game, f, indent=2)


def current_round(game: dict) -> dict | None:
    rounds = game.get("rounds", [])
    idx    = game.get("current_round", 0)
    return rounds[idx] if rounds and idx < len(rounds) else None


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# Admin routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if _hash(pw) == _hash(ADMIN_PASSWORD):
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Wrong password.", "danger")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    game = load_game()
    rd   = current_round(game)
    return render_template("admin/dashboard.html", game=game, rd=rd)


@app.route("/admin/setup", methods=["GET", "POST"])
@admin_required
def admin_setup():
    if request.method == "POST":
        teams_raw = request.form.get("teams", "")
        teams     = [t.strip() for t in teams_raw.split(",") if t.strip()]
        if not teams:
            flash("Enter at least one team name.", "danger")
            return redirect(url_for("admin_setup"))

        # Collect rounds from form  (round_func_0, round_a_0, round_b_0, …)
        rounds_built = []
        idx = 0
        while True:
            func_str = request.form.get(f"round_func_{idx}", "").strip()
            if not func_str:
                break
            a_str    = request.form.get(f"round_a_{idx}", "-2").strip()
            b_str    = request.form.get(f"round_b_{idx}", "2").strip()
            n_pts    = int(request.form.get(f"round_n_{idx}", "6"))
            hint_cost = int(request.form.get(f"round_hcost_{idx}", "50"))
            random_sp = request.form.get(f"round_random_{idx}") == "1"

            try:
                a, b     = float(a_str), float(b_str)
                f_true, expr = parse_function(func_str)
            except (ValueError, Exception) as e:
                flash(f"Round {idx + 1}: {e}", "danger")
                return redirect(url_for("admin_setup"))

            if a >= b:
                flash(f"Round {idx + 1}: a must be < b.", "danger")
                return redirect(url_for("admin_setup"))

            n_pts   = max(2, min(20, n_pts))
            raw_xs  = (np.sort(np.random.uniform(a, b, n_pts)) if random_sp
                       else np.linspace(a, b, n_pts))
            sp      = [(float(px), float(f_true(px))) for px in raw_xs]
            f_std   = function_std(f_true, a, b)
            hints   = generate_hints(expr, a, b)

            rounds_built.append({
                "number":        idx,
                "function":      func_str,
                "interval":      [a, b],
                "sample_points": sp,
                "hints":         hints,
                "hints_revealed": 0,
                "hint_cost":     hint_cost,
                "f_std":         f_std,
                "status":        "pending" if idx > 0 else "active",
            })
            idx += 1

        if not rounds_built:
            flash("Enter at least one round.", "danger")
            return redirect(url_for("admin_setup"))

        game = _blank_game()
        game["teams"]         = teams
        game["rounds"]        = rounds_built
        game["status"]        = "active"
        game["current_round"] = 0
        # Pre-populate submission/score dicts
        for i in range(len(rounds_built)):
            k = str(i)
            game["submissions"][k] = {t: None for t in teams}
            game["scores"][k]      = {}
        save_game(game)
        flash(f"Game set up! {len(rounds_built)} round(s), {len(teams)} team(s).", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin/setup.html")


@app.route("/admin/hint", methods=["POST"])
@admin_required
def admin_hint():
    game = load_game()
    rd   = current_round(game)
    if rd is None:
        flash("No active round.", "danger")
        return redirect(url_for("admin_dashboard"))

    if rd["hints_revealed"] >= len(rd["hints"]):
        flash("All hints already revealed.", "warning")
        return redirect(url_for("admin_dashboard"))

    rd["hints_revealed"] += 1
    save_game(game)
    h = rd["hints"][rd["hints_revealed"] - 1]
    flash(f'Hint revealed: "{h["text"]}"', "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/reveal", methods=["POST"])
@admin_required
def admin_reveal():
    """Score all submissions for current round and mark it revealed."""
    game = load_game()
    rd   = current_round(game)
    if rd is None:
        flash("No active round.", "danger")
        return redirect(url_for("admin_dashboard"))

    if rd["status"] == "revealed":
        flash("Round already revealed.", "warning")
        return redirect(url_for("admin_dashboard"))

    ri   = str(game["current_round"])
    subs = game["submissions"].get(ri, {})

    try:
        f_true, _ = parse_function(rd["function"])
    except Exception:
        flash("Internal error: cannot parse mystery function.", "danger")
        return redirect(url_for("admin_dashboard"))

    a, b    = rd["interval"]
    f_std   = rd["f_std"]
    hcost   = rd["hint_cost"]
    scores  = {}

    for team, sub in subs.items():
        if sub is None:
            scores[team] = {"rmse": None, "accuracy": 0, "penalty": 0, "score": 0}
            continue
        try:
            f_guess, _ = parse_function(sub["expression"])
            rmse       = compute_rmse(f_true, f_guess, a, b)
            hints_used = sub.get("hints_when_submitted", rd["hints_revealed"])
            score      = compute_score(rmse, f_std, hints_used, hcost)
            norm       = rmse / max(f_std, 1e-10)
            accuracy   = round(1000 * math.exp(-2 * norm)) if math.isfinite(rmse) else 0
            penalty    = hints_used * hcost
            scores[team] = {
                "rmse":     float(rmse) if math.isfinite(rmse) else None,
                "accuracy": accuracy,
                "penalty":  penalty,
                "score":    score,
            }
        except Exception:
            scores[team] = {"rmse": None, "accuracy": 0, "penalty": 0, "score": 0}

    game["scores"][ri] = scores
    rd["status"]       = "revealed"
    save_game(game)
    flash("Round revealed! Scores computed.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/next_round", methods=["POST"])
@admin_required
def admin_next_round():
    game = load_game()
    nxt  = game["current_round"] + 1
    if nxt >= len(game["rounds"]):
        game["status"] = "finished"
        save_game(game)
        flash("All rounds complete — game finished!", "success")
        return redirect(url_for("admin_dashboard"))

    game["current_round"] = nxt
    game["rounds"][nxt]["status"] = "active"
    save_game(game)
    flash(f"Advanced to Round {nxt + 1}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/new_game", methods=["POST"])
@admin_required
def admin_new_game():
    if os.path.exists(WEB_GAME_FILE):
        os.remove(WEB_GAME_FILE)
    flash("Game reset. Set up a new game.", "info")
    return redirect(url_for("admin_setup"))


@app.route("/admin/submissions_view")
@admin_required
def admin_submissions_view():
    game = load_game()
    rd   = current_round(game)
    ri   = str(game.get("current_round", 0))
    subs = game.get("submissions", {}).get(ri, {})
    return render_template("admin/submissions.html", game=game, rd=rd, subs=subs)


# ─────────────────────────────────────────────────────────────────────────────
# Team (public) routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    game = load_game()
    if game["status"] == "setup":
        return render_template("waiting.html", message="Game not started yet. Check back soon!")
    rd = current_round(game)
    return render_template("team/index.html", game=game, rd=rd)


@app.route("/submit", methods=["POST"])
def team_submit():
    game = load_game()
    if game["status"] != "active":
        flash("Game is not active right now.", "warning")
        return redirect(url_for("index"))

    rd = current_round(game)
    if rd is None or rd["status"] != "active":
        flash("No active round to submit to.", "warning")
        return redirect(url_for("index"))

    team_name  = request.form.get("team", "").strip()
    expression = request.form.get("expression", "").strip()

    if team_name not in game["teams"]:
        flash(f"Unknown team '{team_name}'.", "danger")
        return redirect(url_for("index"))

    if not expression:
        flash("Enter a function expression.", "danger")
        return redirect(url_for("index"))

    # Validate the expression parses
    try:
        parse_function(expression)
    except Exception as e:
        flash(f"Invalid expression: {e}", "danger")
        return redirect(url_for("index"))

    ri = str(game["current_round"])
    game["submissions"][ri][team_name] = {
        "expression":           expression,
        "hints_when_submitted": rd["hints_revealed"],
        "timestamp":            datetime.now().isoformat(),
    }
    save_game(game)
    return render_template("team/submitted.html", team=team_name, expression=expression)


@app.route("/results")
def results():
    game = load_game()
    rd   = current_round(game)
    ri   = str(game.get("current_round", 0))
    scores = game.get("scores", {}).get(ri, {})
    subs   = game.get("submissions", {}).get(ri, {})

    # Build leaderboard
    ranked = []
    for team in game.get("teams", []):
        sc   = scores.get(team, {})
        sub  = subs.get(team)
        ranked.append({
            "team":       team,
            "score":      sc.get("score", 0) if sc else 0,
            "rmse":       sc.get("rmse"),
            "accuracy":   sc.get("accuracy", 0) if sc else 0,
            "penalty":    sc.get("penalty", 0) if sc else 0,
            "expression": sub["expression"] if sub else None,
        })
    ranked.sort(key=lambda r: -r["score"])

    return render_template("team/results.html", game=game, rd=rd, ranked=ranked)


# ─────────────────────────────────────────────────────────────────────────────
# API endpoint (polling)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/state")
def api_state():
    """Return public game state JSON (no function revealed, no other teams' guesses)."""
    game = load_game()
    rd   = current_round(game)
    ri   = str(game.get("current_round", 0))

    public_rd = None
    if rd:
        revealed_hints = rd["hints"][:rd["hints_revealed"]]
        public_rd = {
            "number":        rd["number"],
            "interval":      rd["interval"],
            "sample_points": rd["sample_points"],
            "hints":         revealed_hints,
            "hints_revealed": rd["hints_revealed"],
            "total_hints":   len(rd["hints"]),
            "hint_cost":     rd["hint_cost"],
            "status":        rd["status"],
            "function":      rd["function"] if rd["status"] == "revealed" else None,
        }

    scores  = game.get("scores", {}).get(ri, {}) if rd and rd.get("status") == "revealed" else {}
    subs    = game.get("submissions", {}).get(ri, {}) if rd and rd.get("status") == "revealed" else {}

    return jsonify({
        "status":        game["status"],
        "current_round": game.get("current_round", 0),
        "total_rounds":  len(game.get("rounds", [])),
        "teams":         game.get("teams", []),
        "round":         public_rd,
        "scores":        scores,
        "submissions":   subs,
    })


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
