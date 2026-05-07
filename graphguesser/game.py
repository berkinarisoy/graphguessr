"""Game state — load and save the session JSON."""
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple

GAME_FILE = "game_session.json"


@dataclass
class Team:
    name: str
    submission: Optional[str] = None
    hints_at_submission: Optional[int] = None
    rmse: Optional[float] = None
    score: Optional[int] = None


@dataclass
class GameState:
    function: str
    interval: Tuple[float, float]
    sample_points: List[Tuple[float, float]]
    hints: List[Dict]
    hints_revealed: int = 0
    hint_cost: int = 50
    teams: Dict[str, Team] = field(default_factory=dict)
    status: str = "active"
    f_std: float = 1.0

    def to_dict(self) -> dict:
        return {
            "function": self.function,
            "interval": list(self.interval),
            "sample_points": [list(p) for p in self.sample_points],
            "hints": self.hints,
            "hints_revealed": self.hints_revealed,
            "hint_cost": self.hint_cost,
            "teams": {name: asdict(t) for name, t in self.teams.items()},
            "status": self.status,
            "f_std": self.f_std,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        d = dict(d)
        teams_raw = d.pop("teams", {})
        teams = {name: Team(**t) for name, t in teams_raw.items()}
        d["interval"] = tuple(d["interval"])
        d["sample_points"] = [tuple(p) for p in d["sample_points"]]
        state = cls(**d)
        state.teams = teams
        return state


def load_game() -> GameState:
    if not os.path.exists(GAME_FILE):
        raise FileNotFoundError(
            f"No game session found ('{GAME_FILE}'). Run  python main.py setup  first."
        )
    with open(GAME_FILE) as f:
        return GameState.from_dict(json.load(f))


def save_game(state: GameState) -> None:
    with open(GAME_FILE, "w") as f:
        json.dump(state.to_dict(), f, indent=2)
