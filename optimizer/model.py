from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model

from config import Config, parse_time


EVENT_KEYS = ("R1", "R2", "R3", "Project", "Design")


@dataclass
class ModelVariables:
    opening_start: Any
    match_day_start: Any
    judging_start: Any
    lunch_start: Any
    closing_start: Any
    finish: Any
    judging_finish: Any
    table_finish: Any
    min_gap: Any
    match_starts: dict[tuple[int, int], Any]
    match_assignments: dict[tuple[int, int, int, int], Any]
    judging_used: dict[tuple[str, int, int], Any]
    judging_starts: dict[tuple[str, int, int], Any]
    judging_assignments: dict[tuple[str, int, int, int], Any]
    team_event_starts: dict[tuple[int, str], Any]
    team_event_ends: dict[tuple[int, str], Any]


@dataclass
class BuiltModel:
    model: cp_model.CpModel
    variables: ModelVariables
    config: Config


def _add_lunch_disjunction(
    model: cp_model.CpModel,
    start: Any,
    duration: int,
    lunch_start: Any,
    lunch_duration: int,
    name: str,
    presence: Any | None = None,
) -> None:
    before = model.NewBoolVar(f"{name}_before_lunch")
    before_conditions = [before]
    after_conditions = [before.Not()]
    if presence is not None:
        before_conditions.append(presence)
        after_conditions.append(presence)
    model.Add(start + duration <= lunch_start).OnlyEnforceIf(before_conditions)
    model.Add(start >= lunch_start + lunch_duration).OnlyEnforceIf(after_conditions)


def build_model(config: Config) -> BuiltModel:
    config.validate()
    model = cp_model.CpModel()
    nteams = config.effective_nteams
    teams = range(nteams)
    rounds = range(3)
    positions = range(2)
    matches = range(nteams // 2)
    horizon = parse_time(config.day.venue_closing_time) if config.day.venue_closing_time else 24 * 60

    opening_low, opening_high = config.opening_window
    judging_low, judging_high = config.judging_window
    match_low, match_high = config.match_window
    lunch_low, lunch_high = config.lunch_window
    closing_low, closing_high = config.closing_window
    opening_start = model.NewIntVar(opening_low, opening_high, "opening_start")
    match_day_start = model.NewIntVar(match_low, match_high, "match_day_start")
    judging_start = model.NewIntVar(judging_low, judging_high, "judging_start")
    lunch_start = model.NewIntVar(lunch_low, lunch_high, "lunch_start")
    closing_start = model.NewIntVar(closing_low, closing_high, "closing_start")
    model.Add(
        judging_start
        >= opening_start
        + config.day.opening_ceremony_duration
    )
    model.Add(match_day_start >= opening_start + config.day.opening_ceremony_duration)

    match_starts: dict[tuple[int, int], Any] = {}
    match_assignments: dict[tuple[int, int, int, int], Any] = {}
    match_presence: dict[tuple[int, int, int], Any] = {}
    durations = (
        config.table.nminutes_table_rnd1,
        config.table.nminutes_table_allrounds,
        config.table.nminutes_table_allrounds,
    )

    for round_index in rounds:
        duration = durations[round_index]
        for match_index in matches:
            start = model.NewIntVar(0, horizon, f"match_r{round_index + 1}_m{match_index + 1}_start")
            match_starts[round_index, match_index] = start
            if match_index:
                model.Add(start >= match_starts[round_index, match_index - 1] + duration)
            _add_lunch_disjunction(
                model,
                start,
                duration,
                lunch_start,
                config.day.nminutes_lunch,
                f"match_r{round_index + 1}_m{match_index + 1}",
            )
            for position in positions:
                assignment_vars = []
                for team in teams:
                    variable = model.NewBoolVar(
                        f"match_r{round_index + 1}_m{match_index + 1}_p{position + 1}_t{team + 1}"
                    )
                    match_assignments[round_index, match_index, position, team] = variable
                    assignment_vars.append(variable)
                model.Add(sum(assignment_vars) == 1)

            for team in teams:
                present = model.NewBoolVar(
                    f"match_r{round_index + 1}_m{match_index + 1}_t{team + 1}_present"
                )
                match_presence[round_index, match_index, team] = present
                model.Add(
                    present
                    == sum(
                        match_assignments[round_index, match_index, position, team]
                        for position in positions
                    )
                )

        for team in teams:
            model.Add(
                sum(match_presence[round_index, match_index, team] for match_index in matches)
                == 1
            )

    # Anonymous team identities are interchangeable. Canonicalize Round 1 to
    # remove a large amount of equivalent search without restricting schedules.
    for match_index in matches:
        model.Add(match_assignments[0, match_index, 0, 2 * match_index] == 1)
        model.Add(match_assignments[0, match_index, 1, 2 * match_index + 1] == 1)

    model.Add(match_starts[0, 0] == match_day_start)
    for round_index in (1, 2):
        previous_end = (
            match_starts[round_index - 1, nteams // 2 - 1]
            + durations[round_index - 1]
        )
        model.Add(
            match_starts[round_index, 0]
            >= previous_end + config.table.match_break_duration
        )

    # Every team uses both physical table positions across its three rounds.
    for team in teams:
        for position in positions:
            model.Add(
                sum(
                    match_assignments[round_index, match_index, position, team]
                    for round_index in rounds
                    for match_index in matches
                )
                >= 1
            )

    # Pairwise opponent uniqueness.
    for first_team in teams:
        for second_team in range(first_team + 1, nteams):
            meetings = []
            for round_index in rounds:
                for match_index in matches:
                    meeting = model.NewBoolVar(
                        f"meeting_t{first_team + 1}_t{second_team + 1}_r{round_index + 1}_m{match_index + 1}"
                    )
                    first_present = match_presence[round_index, match_index, first_team]
                    second_present = match_presence[round_index, match_index, second_team]
                    model.Add(meeting <= first_present)
                    model.Add(meeting <= second_present)
                    model.Add(meeting >= first_present + second_present - 1)
                    meetings.append(meeting)
            model.Add(sum(meetings) <= 1)

    judging_used: dict[tuple[str, int, int], Any] = {}
    judging_starts: dict[tuple[str, int, int], Any] = {}
    judging_assignments: dict[tuple[str, int, int, int], Any] = {}
    judging_types = ("Project", "Design")
    room_count = config.tournament.njudging_rooms
    active_room_count = min(room_count, max(1, nteams // 2))
    slots = range(nteams)
    judging_duration = config.judging.nminutes_judging

    for judging_type in judging_types:
        for room in range(room_count):
            # Project and Design start together. Keep the number of simultaneous
            # first-wave appointments at or below the number of teams.
            active_room = room < active_room_count
            for slot in slots:
                used = model.NewBoolVar(f"{judging_type}_room{room + 1}_slot{slot + 1}_used")
                start = model.NewIntVar(0, horizon, f"{judging_type}_room{room + 1}_slot{slot + 1}_start")
                judging_used[judging_type, room, slot] = used
                judging_starts[judging_type, room, slot] = start
                assignments = []
                for team in teams:
                    assigned = model.NewBoolVar(
                        f"{judging_type}_room{room + 1}_slot{slot + 1}_t{team + 1}"
                    )
                    judging_assignments[judging_type, room, slot, team] = assigned
                    assignments.append(assigned)
                model.Add(sum(assignments) == used)
                if slot == 0:
                    model.Add(used == int(active_room))
                    if active_room:
                        model.Add(start == judging_start)
                else:
                    model.Add(used <= judging_used[judging_type, room, slot - 1])
                    previous_start = judging_starts[judging_type, room, slot - 1]
                    gap = config.judging.nminutes_between_judging
                    if slot % config.judging.nteams_per_judging_sprint == 0:
                        gap += config.judging.extra_sprint_break
                    model.Add(start >= previous_start + judging_duration + gap).OnlyEnforceIf(used)
                _add_lunch_disjunction(
                    model,
                    start,
                    judging_duration,
                    lunch_start,
                    config.day.nminutes_lunch,
                    f"{judging_type}_room{room + 1}_slot{slot + 1}",
                    used,
                )
        for team in teams:
            model.Add(
                sum(
                    judging_assignments[judging_type, room, slot, team]
                    for room in range(room_count)
                    for slot in slots
                )
                == 1
            )

    team_event_starts: dict[tuple[int, str], Any] = {}
    team_event_ends: dict[tuple[int, str], Any] = {}
    all_ends = []
    judging_ends = []
    table_ends = []
    event_durations = {
        "R1": durations[0],
        "R2": durations[1],
        "R3": durations[2],
        "Project": judging_duration,
        "Design": judging_duration,
    }
    for team in teams:
        for event_key in EVENT_KEYS:
            start = model.NewIntVar(0, horizon, f"team{team + 1}_{event_key}_start")
            end = model.NewIntVar(0, horizon, f"team{team + 1}_{event_key}_end")
            model.Add(end == start + event_durations[event_key])
            team_event_starts[team, event_key] = start
            team_event_ends[team, event_key] = end
            all_ends.append(end)
            if event_key in {"Project", "Design"}:
                judging_ends.append(end)
            else:
                table_ends.append(end)

        for round_index, event_key in enumerate(("R1", "R2", "R3")):
            for match_index in matches:
                model.Add(
                    team_event_starts[team, event_key] == match_starts[round_index, match_index]
                ).OnlyEnforceIf(match_presence[round_index, match_index, team])

        for judging_type in judging_types:
            for room in range(room_count):
                for slot in slots:
                    model.Add(
                        team_event_starts[team, judging_type]
                        == judging_starts[judging_type, room, slot]
                    ).OnlyEnforceIf(judging_assignments[judging_type, room, slot, team])

    min_gap = model.NewIntVar(config.team.time_between_events, horizon, "minimum_team_gap")
    for team in teams:
        for first_index, first_event in enumerate(EVENT_KEYS):
            for second_event in EVENT_KEYS[first_index + 1 :]:
                if first_event.startswith("R") and second_event.startswith("R"):
                    model.Add(
                        team_event_starts[team, second_event]
                        >= team_event_ends[team, first_event] + min_gap
                    )
                    continue
                first_before = model.NewBoolVar(
                    f"team{team + 1}_{first_event}_before_{second_event}"
                )
                model.Add(
                    team_event_starts[team, second_event]
                    >= team_event_ends[team, first_event] + min_gap
                ).OnlyEnforceIf(first_before)
                model.Add(
                    team_event_starts[team, first_event]
                    >= team_event_ends[team, second_event] + min_gap
                ).OnlyEnforceIf(first_before.Not())

    finish = model.NewIntVar(0, horizon, "competitive_finish")
    judging_finish = model.NewIntVar(0, horizon, "judging_finish")
    table_finish = model.NewIntVar(0, horizon, "table_finish")
    model.AddMaxEquality(finish, all_ends)
    model.AddMaxEquality(judging_finish, judging_ends)
    model.AddMaxEquality(table_finish, table_ends)
    model.Add(closing_start >= finish)
    model.Add(closing_start >= judging_finish + config.day.deliberation_duration)
    if config.day.venue_closing_time:
        model.Add(
            closing_start + config.day.closing_ceremony_duration
            <= parse_time(config.day.venue_closing_time)
        )

    variables = ModelVariables(
        opening_start=opening_start,
        match_day_start=match_day_start,
        judging_start=judging_start,
        lunch_start=lunch_start,
        closing_start=closing_start,
        finish=finish,
        judging_finish=judging_finish,
        table_finish=table_finish,
        min_gap=min_gap,
        match_starts=match_starts,
        match_assignments=match_assignments,
        judging_used=judging_used,
        judging_starts=judging_starts,
        judging_assignments=judging_assignments,
        team_event_starts=team_event_starts,
        team_event_ends=team_event_ends,
    )
    return BuiltModel(model=model, variables=variables, config=config)
