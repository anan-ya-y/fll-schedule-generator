from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import time
import json
from pathlib import Path
from typing import Any


def parse_time(value: str | time | int) -> int:
    """Convert HH:MM[:SS], datetime.time, or minute integers to minutes."""
    if isinstance(value, int):
        return value
    if isinstance(value, time):
        return value.hour * 60 + value.minute
    parts = [int(part) for part in value.split(":")]
    if len(parts) not in (2, 3):
        raise ValueError(f"Invalid time {value!r}; expected HH:MM or HH:MM:SS")
    return parts[0] * 60 + parts[1]


def minute_to_time(value: int) -> time:
    return time((value // 60) % 24, value % 60)


@dataclass
class TournamentSettings:
    nteams: int = 20
    njudging_rooms: int = 2
    ntables: int = 2
    ntable_rounds: int = 3


@dataclass
class TableSettings:
    match_break_duration: int = 10
    nminutes_execution: int = 5
    nminutes_table_rnd1: int = 10
    nminutes_table_allrounds: int = 8


@dataclass
class JudgingSettings:
    nminutes_judging: int = 10
    nminutes_between_judging: int = 10
    nteams_per_judging_sprint: int = 3
    extra_sprint_break: int = 5


@dataclass
class DaySettings:
    start_time: str = "09:00"
    opening_ceremony_duration: int = 20
    judging_start_time: str | None = None
    matches_start_time: str = "09:30"
    matches_start_time_latest: str | None = None
    lunch_start: str = "12:00"
    lunch_start_latest: str | None = None
    nminutes_lunch: int = 60
    closing_ceremony_time: str = "15:30"
    closing_ceremony_time_latest: str | None = "18:00"
    deliberation_duration: int = 0


@dataclass
class TeamSettings:
    time_between_events: int = 20


@dataclass
class SolverSettings:
    max_time_seconds: float = 60.0
    num_search_workers: int = 8
    random_seed: int = 2025
    finish_allowance: int = 0
    objective_mode: str = "lexicographic"
    overall_finish_weight: int = 10
    judging_separation_weight: int = 5
    table_diversity_weight: int = 1
    minimum_gap_weight: int = 1
    log_search_progress: bool = False


@dataclass
class Config:
    tournament: TournamentSettings = field(default_factory=TournamentSettings)
    table: TableSettings = field(default_factory=TableSettings)
    judging: JudgingSettings = field(default_factory=JudgingSettings)
    day: DaySettings = field(default_factory=DaySettings)
    team: TeamSettings = field(default_factory=TeamSettings)
    solver: SolverSettings = field(default_factory=SolverSettings)

    def validate(self) -> None:
        tournament = self.tournament
        if tournament.ntables < 2 or tournament.ntables % 2:
            raise ValueError(
                "ntables must be an even number of physical tables (at least 2)"
            )
        if tournament.ntable_rounds != 3:
            raise ValueError("The optimizer currently requires exactly three table rounds")
        if tournament.nteams <= 0:
            raise ValueError("nteams must be positive")
        if tournament.njudging_rooms <= 0:
            raise ValueError("njudging_rooms must be positive")
        if self.team.time_between_events < 0:
            raise ValueError("time_between_events cannot be negative")
        if self.table.nminutes_execution <= 0:
            raise ValueError("nminutes_execution must be positive")
        if self.table.nminutes_execution > min(
            self.table.nminutes_table_rnd1,
            self.table.nminutes_table_allrounds,
        ):
            raise ValueError(
                "nminutes_execution cannot exceed the total table duration"
            )
        if self.judging.nteams_per_judging_sprint <= 0:
            raise ValueError("nteams_per_judging_sprint must be positive")
        if self.day.opening_ceremony_duration < 0:
            raise ValueError("opening_ceremony_duration cannot be negative")
        if self.solver.objective_mode not in {"lexicographic", "weighted"}:
            raise ValueError("objective_mode must be 'lexicographic' or 'weighted'")
        objective_weights = (
            self.solver.overall_finish_weight,
            self.solver.judging_separation_weight,
            self.solver.table_diversity_weight,
            self.solver.minimum_gap_weight,
        )
        if any(weight < 0 for weight in objective_weights):
            raise ValueError("objective weights cannot be negative")
        if self.solver.objective_mode == "weighted" and not any(objective_weights):
            raise ValueError("weighted objective mode requires at least one positive weight")

        opening_earliest, opening_latest = self.opening_window
        judging_earliest, judging_latest = self.judging_window
        match_earliest, match_latest = self.match_window
        lunch_earliest, lunch_latest = self.lunch_window
        closing_earliest, closing_latest = self.closing_window
        for name, earliest, latest in (
            ("opening", opening_earliest, opening_latest),
            ("judging", judging_earliest, judging_latest),
            ("match", match_earliest, match_latest),
            ("lunch", lunch_earliest, lunch_latest),
            ("closing", closing_earliest, closing_latest),
        ):
            if latest < earliest:
                raise ValueError(f"{name} latest time must not precede its earliest time")

        opening_end = opening_earliest + self.day.opening_ceremony_duration
        if judging_earliest < opening_end:
            raise ValueError(
                "judging_start_time must be at or after the opening ceremony"
            )
        if match_latest < opening_end:
            raise ValueError(
                "matches_start_time window must allow matches to start after "
                "the opening ceremony"
            )

    @property
    def effective_nteams(self) -> int:
        if self.tournament.nteams % 2:
            return self.tournament.nteams + 1
        return self.tournament.nteams

    @staticmethod
    def _window(earliest: str, latest: str | None) -> tuple[int, int]:
        lower = parse_time(earliest)
        return lower, parse_time(latest) if latest else lower

    @property
    def opening_window(self) -> tuple[int, int]:
        # Opening is a fixed ceremony, not an optimizable window.
        start = parse_time(self.day.start_time)
        return start, start

    @property
    def judging_window(self) -> tuple[int, int]:
        if self.day.judging_start_time is not None:
            start = parse_time(self.day.judging_start_time)
        else:
            start = (
                parse_time(self.day.start_time)
                + self.day.opening_ceremony_duration
            )
        return start, start

    @property
    def match_window(self) -> tuple[int, int]:
        return self._window(self.day.matches_start_time, self.day.matches_start_time_latest)

    @property
    def lunch_window(self) -> tuple[int, int]:
        return self._window(self.day.lunch_start, self.day.lunch_start_latest)

    @property
    def closing_window(self) -> tuple[int, int]:
        return self._window(
            self.day.closing_ceremony_time,
            self.day.closing_ceremony_time_latest,
        )

    @classmethod
    def from_json(cls, filename: str | Path) -> "Config":
        with open(filename, encoding="utf-8") as handle:
            data = json.load(handle)
        config = cls()
        config._apply_mapping(data)
        config.validate()
        return config

    def _apply_mapping(self, data: dict[str, Any]) -> None:
        sections = {
            "tournament": self.tournament,
            "table": self.table,
            "judging": self.judging,
            "day": self.day,
            "team": self.team,
            "solver": self.solver,
        }
        for section_name, target in sections.items():
            for key, value in data.get(section_name, {}).items():
                if hasattr(target, key):
                    setattr(target, key, value)

    def to_dict(self) -> dict[str, Any]:
        def serialize(value: Any) -> Any:
            if isinstance(value, time):
                return value.strftime("%H:%M:%S")
            if isinstance(value, dict):
                return {key: serialize(item) for key, item in value.items()}
            if isinstance(value, list):
                return [serialize(item) for item in value]
            return value

        return serialize(asdict(self))

    def to_json(self, filename: str | Path) -> None:
        with open(filename, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=4)

