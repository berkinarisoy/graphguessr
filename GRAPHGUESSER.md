# GraphGuesser — Game Rules & Design

## What Is GraphGuesser?

GraphGuesser is a team math game where a **host** defines a secret function f(x) and teams try to identify it from clues. Teams compete to reconstruct the function as accurately as possible, earning higher scores for precision and for guessing early (before too many hints are given).

---

## Roles

| Role | Responsibilities |
|------|-----------------|
| **Host** | Picks f(x), interval [a, b], sample points, and a ranked list of hints. Runs the game software. Never reveals the function until the end. |
| **Team** | Studies the sample points, discusses, and submits a function expression. May wait for hints at the cost of a score penalty. |

---

## Setup (Before the Game)

1. The host picks a **mystery function** f(x) — any mathematical expression (polynomial, trig, exponential, etc.).
2. The host chooses an **interval** [a, b] on which the game is played.
3. The host selects **n sample points** (x, f(x)) — typically 4 to 8 points, evenly or randomly spaced. These are the only information teams start with.
4. The host software auto-generates a menu of **hints** sorted from least to most revealing. The host selects which hints to use and in what order.
5. The host sets a **hint penalty** (default: 50 points per hint revealed).
6. Team names are registered.

A **sample-points plot** is displayed or projected for all teams.

---

## Game Flow

The game proceeds in **rounds**. Each round ends when the host reveals the next hint.

```
Round 0  → Sample points shown (no hints yet)
Round 1  → Hint 1 revealed
Round 2  → Hint 2 revealed
  ...
Round k  → Hint k revealed  (last hint)
```

Teams may **lock in their final answer at any point** — after seeing the sample points alone, after any hint, or at the very end. The score depends on when they submit: submitting early (fewer hints seen) yields a higher score if the guess is accurate.

The host controls pacing. A suggested timer is **3–5 minutes per round**.

---

## Hints System

Hints are auto-generated from the true function and ordered by the host from weakest to strongest. Each hint revealed adds a flat penalty to all teams' final scores.

### Available Hint Types

| Type | Example |
|------|---------|
| **Function family** | "The function is a cubic polynomial." |
| **Symmetry** | "The function is odd: f(-x) = −f(x)." |
| **Definite integral** | "∫f(x)dx over [−2, 2] ≈ 0.0000" |
| **Zeros / Roots** | "f has roots at x ≈ −1.0000, 0.0000" |
| **Derivative at midpoint** | "f′(0) ≈ −3.0000" |
| **Local extrema** | "Local minimum at (0.707, −1.414)" |
| **Concavity** | "f″(0) ≈ 12.0; the function is concave up near the midpoint." |

### Hint Penalty Rule

> Each hint that has been **revealed by the time a team submits** costs the team `hint_cost` points.
>
> A team that submits before any hint is revealed pays **no penalty**.  
> A team that waits for all k hints pays **k × hint_cost** points.

This creates a risk/reward tension: hints help accuracy but hurt your ceiling score.

---

## Scoring Formula

### Step 1 — Accuracy score

The host software evaluates both functions on 5 000 evenly spaced points across [a, b] and computes the **RMSE**:

$$\text{RMSE} = \sqrt{\frac{1}{n}\sum_{i=1}^{n}\bigl(f(x_i) - g(x_i)\bigr)^2}$$

where f is the true function and g is the team's guess. The RMSE is **normalized** by the standard deviation of f on [a, b] to make it scale-independent:

$$\tilde{\varepsilon} = \frac{\text{RMSE}}{\sigma_f}$$

The raw accuracy score (0 – 1000) is then:

$$\text{accuracy} = \lfloor 1000 \cdot e^{-2\tilde{\varepsilon}} \rceil$$

| Normalized RMSE | Accuracy |
|-----------------|----------|
| 0 (perfect) | 1000 |
| 0.25 | 607 |
| 0.5 | 368 |
| 1.0 | 135 |
| 2.0 | 18 |

### Step 2 — Hint penalty

$$\text{penalty} = \text{hints\_revealed} \times \text{hint\_cost}$$

### Step 3 — Final score

$$\boxed{\text{score} = \max\bigl(0,\ \text{accuracy} - \text{penalty}\bigr)}$$

### Tie-breaking

If two teams have the same score, the one with the lower RMSE wins. If still tied, the team that submitted earlier (fewer hints revealed) wins.

---

## Winning

The team with the **highest score** wins the round. Play multiple rounds (with different functions) and accumulate points across rounds for a full game night tournament.

### Suggested multi-round format

- 3–5 rounds, increasing difficulty.
- Functions should vary in type: one polynomial, one trig, one mixed, etc.
- The host can optionally announce the function *family* at the start of harder rounds.

---

## Additional Rules & Clarifications

- **Expression syntax**: Teams write functions using standard math notation: `x**2`, `sin(x)`, `exp(-x)`, `log(x)`, `sqrt(x)`, `pi`, `e`.
- **Allowed functions**: Any expression that can be evaluated numerically over the interval.
- **Invalid submissions**: A submission that produces errors (division by zero everywhere, undefined domain over the whole interval, etc.) scores 0.
- **Re-submissions**: Teams may update their submission any number of times. Only their **last** submission before the reveal counts.
- **Partial credit**: The exponential scoring formula always gives some credit for a reasonable guess — there are no all-or-nothing rulings.

---

## Quick CLI Reference

```
python main.py setup           # Host: create a new game session
python main.py start           # Host: display sample points to teams
python main.py hint            # Host: reveal the next hint
python main.py hints           # Show all hints revealed so far
python main.py submit TEAM EXPR  # Enter a team's guess
python main.py scores          # Show current leaderboard
python main.py reveal          # End game, show answer + final plots
```

---

## Example Game

**Host setup**

```
Function:  2*x**3 - 3*x + 1
Interval:  [-2, 2]
Points:    5 sample points (evenly spaced)
Hints:     symmetry → roots → integral → derivative → extrema
Hint cost: 50 pts
Teams:     Alpha, Beta, Gamma
```

**Sample points shown:**

| x | f(x) |
|---|------|
| −2.0 | −9.0 |
| −1.0 | 4.0 |
| 0.0 | 1.0 |
| 1.0 | 0.0 |
| 2.0 | 11.0 |

**Round 0** — Teams see the points. Beta immediately guesses `x**3 - x + 1` (close but wrong leading coefficient). Alpha waits.

**Round 1** — Hint: *"The function is odd: f(−x) = −f(x)."*  
Wait — the function `2x³ − 3x + 1` is **not** odd because of the `+1` constant. The hint correctly says "no special symmetry." Teams update guesses.

**Round 2** — Hint: *"Roots at x ≈ −1.3573, 0.3527, 0.9060."*  
Alpha locks in `2*x**3 - 3*x + 1` (correct!).

**Final scores:**

| Team | Submission | RMSE | Accuracy | Hints | Score |
|------|-----------|------|----------|-------|-------|
| Alpha | `2*x**3 - 3*x + 1` | 0.000 | 1000 | 2 (−100) | **900** |
| Beta | `x**3 - x + 1` | 1.247 | 298 | 3 (−150) | **148** |
| Gamma | `2*x**3 - 3*x` | 0.289 | 814 | 4 (−200) | **614** |

Alpha wins by submitting the correct function early!
