from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
from ortools.sat.python import cp_model

from config import Config, minute_to_time
from optimizer.model import BuiltModel, build_model


class OptimizationError(RuntimeError):
    pass


@dataclass
class SolveStage:
    status: str
    objective: int | None
    wall_time_seconds: float
    best_bound: float | None


@dataclass
class OptimizationResult:
    events: pd.DataFrame
    config: Config
    stages: dict[str, SolveStage]
    minimum_gap: int
    finish: int
    judging_finish: int
    table_finish: int
    table_diversity: int
    judging_table_separation: int
    opening_start: int
    judging_start: int
    match_start: int
    lunch_start: int
    closing_start: int

    def metrics(self) -> dict[str, Any]:
        return {
            "stages": {
                name: {
                    "status": stage.status,
                    "objective": stage.objective,
                    "best_bound": stage.best_bound,
                    "wall_time_seconds": stage.wall_time_seconds,
                }
                for name, stage in self.stages.items()
            },
            "minimum_gap": self.minimum_gap,
            "finish_minute": self.finish,
            "judging_finish_minute": self.judging_finish,
            "table_finish_minute": self.table_finish,
            "distinct_team_table_assignments": self.table_diversity,
            "judging_table_separation_minutes": self.judging_table_separation,
            "opening_start_minute": self.opening_start,
            "judging_start_minute": self.judging_start,
            "match_start_minute": self.match_start,
            "lunch_start_minute": self.lunch_start,
            "closing_start_minute": self.closing_start,
        }


def _new_solver(config: Config) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config.solver.max_time_seconds
    solver.parameters.num_search_workers = config.solver.num_search_workers
    solver.parameters.random_seed = config.solver.random_seed
    solver.parameters.log_search_progress = config.solver.log_search_progress
    return solver


def _stage(solver: cp_model.CpSolver, status: Any, objective: int | None) -> SolveStage:
    feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    return SolveStage(
        status=solver.StatusName(status),
        objective=objective,
        best_bound=solver.BestObjectiveBound() if feasible else None,
        wall_time_seconds=solver.WallTime(),
    )


def optimize(config: Config) -> OptimizationResult:
    built = build_model(config)
    model = built.model
    variables = built.variables

    if config.solver.objective_mode == "weighted":
        weighted_objective = (
            config.solver.overall_finish_weight * variables.finish
            - config.solver.judging_separation_weight
            * (variables.table_finish - variables.judging_finish)
            - config.solver.table_diversity_weight * variables.table_diversity
            - config.solver.minimum_gap_weight * variables.min_gap
        )
        model.Minimize(weighted_objective)
        solver = _new_solver(config)
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise OptimizationError(
                f"Weighted-objective solve ended with {solver.StatusName(status)}"
            )
        stages = {
            "weighted_objective": _stage(
                solver,
                status,
                int(round(solver.ObjectiveValue())),
            )
        }
        return _result(built, solver, stages)

    model.Minimize(variables.finish)
    first_solver = _new_solver(config)
    first_status = first_solver.Solve(model)
    if first_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise OptimizationError(
            f"Earliest-finish solve ended with {first_solver.StatusName(first_status)}"
        )
    first_value = first_solver.Value(variables.finish)
    stages = {
        "earliest_finish": _stage(first_solver, first_status, first_value),
    }

    model.Add(
        variables.finish <= first_value + config.solver.finish_allowance
    )

    judging_separation = variables.table_finish - variables.judging_finish
    model.Maximize(judging_separation)
    judging_solver = _new_solver(config)
    judging_status = judging_solver.Solve(model)
    if judging_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        separation_value = judging_solver.Value(judging_separation)
        stages["maximum_judging_table_separation"] = _stage(
            judging_solver,
            judging_status,
            separation_value,
        )
        model.Add(judging_separation >= separation_value)
        fallback_solver = judging_solver
    else:
        stages["maximum_judging_table_separation"] = _stage(
            judging_solver,
            judging_status,
            None,
        )
        fallback_solver = first_solver

    model.Maximize(variables.table_diversity)
    diversity_solver = _new_solver(config)
    diversity_status = diversity_solver.Solve(model)
    if diversity_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        diversity_value = diversity_solver.Value(variables.table_diversity)
        stages["maximum_table_diversity"] = _stage(
            diversity_solver,
            diversity_status,
            diversity_value,
        )
        model.Add(variables.table_diversity >= diversity_value)
        fallback_solver = diversity_solver
    else:
        stages["maximum_table_diversity"] = _stage(
            diversity_solver,
            diversity_status,
            None,
        )

    model.Maximize(variables.min_gap)
    gap_solver = _new_solver(config)
    gap_status = gap_solver.Solve(model)
    if gap_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        solver = gap_solver
        stages["maximum_minimum_gap"] = _stage(
            gap_solver,
            gap_status,
            gap_solver.Value(variables.min_gap),
        )
    else:
        solver = fallback_solver
        stages["maximum_minimum_gap"] = _stage(gap_solver, gap_status, None)

    return _result(built, solver, stages)


def _result(
    built: BuiltModel,
    solver: cp_model.CpSolver,
    stages: dict[str, SolveStage],
) -> OptimizationResult:
    config = built.config
    variables = built.variables
    events = _extract_anonymous_events(built, solver)
    finish = solver.Value(variables.finish)
    judging_finish = solver.Value(variables.judging_finish)
    table_finish = solver.Value(variables.table_finish)
    closing_start = max(
        config.closing_window[0],
        finish,
        judging_finish + config.day.deliberation_duration,
    )
    return OptimizationResult(
        events=events,
        config=config,
        stages=stages,
        minimum_gap=solver.Value(variables.min_gap),
        finish=finish,
        judging_finish=judging_finish,
        table_finish=table_finish,
        table_diversity=solver.Value(variables.table_diversity),
        judging_table_separation=table_finish - judging_finish,
        opening_start=solver.Value(variables.opening_start),
        judging_start=solver.Value(variables.judging_start),
        match_start=solver.Value(variables.match_day_start),
        lunch_start=solver.Value(variables.lunch_start),
        closing_start=closing_start,
    )


def _extract_anonymous_events(
    built: BuiltModel,
    solver: cp_model.CpSolver,
) -> pd.DataFrame:
    config = built.config
    variables = built.variables
    nteams = config.effective_nteams
    rows: list[dict[str, Any]] = []
    durations = (
        config.table.nminutes_table_rnd1,
        config.table.nminutes_table_allrounds,
        config.table.nminutes_table_allrounds,
    )
    table_names = [
        f"Table {index + 1}" for index in range(config.tournament.ntables)
    ]

    for round_index in range(3):
        for match_index in range(nteams // 2):
            start = solver.Value(variables.match_starts[round_index, match_index])
            for table, table_name in enumerate(table_names):
                assigned_teams = [
                    team
                    for team in range(nteams)
                    if solver.BooleanValue(
                        variables.match_assignments[
                            round_index, match_index, table, team
                        ]
                    )
                ]
                if not assigned_teams:
                    continue
                team = assigned_teams[0]
                rows.append(
                    {
                        "Time": minute_to_time(start),
                        "EventName": "Table",
                        "RoundNo": round_index + 1,
                        "Room": table_name,
                        "Duration": durations[round_index],
                        "Team": team + 1,
                    }
                )
        if round_index < 2 and config.table.match_break_duration > 0:
            break_start = (
                solver.Value(
                    variables.match_starts[round_index, nteams // 2 - 1]
                )
                + durations[round_index]
            )
            next_round_start = solver.Value(
                variables.match_starts[round_index + 1, 0]
            )
            if next_round_start - break_start <= config.table.match_break_duration:
                for table_name in table_names:
                    rows.append(
                        {
                            "Time": minute_to_time(break_start),
                            "EventName": "Break",
                            "RoundNo": 0,
                            "Room": table_name,
                            "Duration": config.table.match_break_duration,
                            "Team": -2,
                        }
                    )

    room_names = {
        judging_type: [
            f"{judging_type} {index + 1}"
            for index in range(config.tournament.njudging_rooms)
        ]
        for judging_type in ("Project", "Design")
    }
    for judging_type, names in room_names.items():
        for room_index, room_name in enumerate(names):
            used_slots = []
            for slot in range(nteams):
                used = variables.judging_used[judging_type, room_index, slot]
                if not solver.BooleanValue(used):
                    continue
                start = solver.Value(
                    variables.judging_starts[judging_type, room_index, slot]
                )
                team = next(
                    team
                    for team in range(nteams)
                    if solver.BooleanValue(
                        variables.judging_assignments[
                            judging_type, room_index, slot, team
                        ]
                    )
                )
                rows.append(
                    {
                        "Time": minute_to_time(start),
                        "EventName": judging_type,
                        "RoundNo": 0,
                        "Room": room_name,
                        "Duration": config.judging.nminutes_judging,
                        "Team": team + 1,
                    }
                )
                used_slots.append((slot, start))
            for index, (slot, start) in enumerate(used_slots[:-1]):
                if (slot + 1) % config.judging.nteams_per_judging_sprint != 0:
                    continue
                if config.judging.extra_sprint_break <= 0:
                    continue
                next_start = used_slots[index + 1][1]
                actual_gap = (
                    next_start - start - config.judging.nminutes_judging
                )
                required_gap = (
                    config.judging.nminutes_between_judging
                    + config.judging.extra_sprint_break
                )
                if actual_gap > required_gap:
                    continue
                rows.append(
                    {
                        "Time": minute_to_time(
                            start
                            + config.judging.nminutes_judging
                            + config.judging.nminutes_between_judging
                        ),
                        "EventName": "Break",
                        "RoundNo": 0,
                        "Room": room_name,
                        "Duration": config.judging.extra_sprint_break,
                        "Team": -2,
                    }
                )

    lunch_start = solver.Value(variables.lunch_start)
    all_rooms = table_names + room_names["Project"] + room_names["Design"]
    for room in all_rooms:
        if config.day.nminutes_lunch <= 0:
            continue
        room_activities = [
            row
            for row in rows
            if row["Room"] == room
            and row["EventName"] in {"Table", "Project", "Design"}
        ]
        if not room_activities:
            continue
        first_start = min(
            activity["Time"].hour * 60 + activity["Time"].minute
            for activity in room_activities
        )
        last_end = max(
            activity["Time"].hour * 60
            + activity["Time"].minute
            + int(activity["Duration"])
            for activity in room_activities
        )
        if not (first_start < lunch_start and last_end > lunch_start):
            continue
        rows.append(
            {
                "Time": minute_to_time(lunch_start),
                "EventName": "Lunch",
                "RoundNo": 0,
                "Room": room,
                "Duration": config.day.nminutes_lunch,
                "Team": -2,
            }
        )

    events = pd.DataFrame(
        rows,
        columns=["Time", "EventName", "RoundNo", "Room", "Duration", "Team"],
    )
    return events.sort_values("Time", kind="stable").reset_index(drop=True)
