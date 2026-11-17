from __future__ import annotations

from dataclasses import dataclass
from datetime import time

import pandas as pd

from config import Config, parse_time
from schedule import Tournament


@dataclass
class ValidationReport:
    minimum_gap: int
    limiting_team: int
    limiting_events: tuple[str, str]


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def validate_tournament(tournament: Tournament) -> ValidationReport:
    events = tournament.events
    config = tournament.config
    required_columns = {
        "Time",
        "EventName",
        "RoundNo",
        "Room",
        "Duration",
        "Team",
        "Team ID",
        "TeamName",
        "Note",
    }
    missing = sorted(required_columns - set(events.columns))
    if missing:
        raise ValueError(f"Schedule is missing columns: {', '.join(missing)}")
    if (events["Team"] == -1).any():
        raise ValueError("Final schedule contains unassigned team slots")

    competitive = events[events["EventName"].isin(["Table", "Project", "Design"])]
    expected_ids = set(range(1, config.effective_nteams + 1))
    if set(competitive["Team ID"].unique()) != expected_ids:
        raise ValueError("Competitive events do not contain exactly the expected template teams")

    minimum_gap = 10**9
    limiting_team = -1
    limiting_events = ("", "")
    for team_id in sorted(expected_ids):
        team_events = competitive[competitive["Team ID"] == team_id].sort_values("Time")
        counts = team_events["EventName"].value_counts().to_dict()
        if counts != {"Table": 3, "Project": 1, "Design": 1}:
            raise ValueError(f"Template team {team_id} has incorrect event counts: {counts}")
        rounds = sorted(team_events.loc[team_events["EventName"] == "Table", "RoundNo"])
        if rounds != [1, 2, 3]:
            raise ValueError(f"Template team {team_id} has incorrect table rounds: {rounds}")
        table_names = set(team_events.loc[team_events["EventName"] == "Table", "Room"])
        if len(table_names) < 2:
            raise ValueError(f"Template team {team_id} does not use at least two tables")

        records = list(team_events.itertuples(index=False))
        for previous, current in zip(records, records[1:]):
            previous_end = _minutes(previous.Time) + int(previous.Duration)
            gap = _minutes(current.Time) - previous_end
            if gap < config.team.time_between_events:
                raise ValueError(
                    f"Template team {team_id} has only {gap} minutes between events"
                )
            if gap < minimum_gap:
                minimum_gap = gap
                limiting_team = int(current.Team)
                limiting_events = (
                    _event_label(previous.EventName, previous.RoundNo),
                    _event_label(current.EventName, current.RoundNo),
                )

    table_events = competitive[competitive["EventName"] == "Table"]
    expected_table_durations = {
        1: config.table.nminutes_table_rnd1,
        2: config.table.nminutes_table_allrounds,
        3: config.table.nminutes_table_allrounds,
    }
    for row in table_events.itertuples(index=False):
        if int(row.Duration) != expected_table_durations[int(row.RoundNo)]:
            raise ValueError(f"Incorrect duration for Table Round {row.RoundNo}")
    table_pairs = {
        frozenset(config.tournament.table_names[index : index + 2])
        for index in range(0, config.tournament.ntables, 2)
    }
    opponents: set[tuple[int, int]] = set()
    for (round_no, start), match in table_events.groupby(["RoundNo", "Time"]):
        rooms = set(match["Room"])
        if (
            len(match) != 2
            or len(rooms) != 2
            or frozenset(rooms) not in table_pairs
        ):
            raise ValueError(
                f"Round {round_no} at {start} does not use one complete table pair"
            )
        pair = tuple(sorted(int(value) for value in match["Team ID"]))
        if pair in opponents:
            raise ValueError(f"Repeated opponent pairing: {pair}")
        opponents.add(pair)

    match_starts = sorted({_minutes(value) for value in table_events["Time"]})
    for previous, current in zip(match_starts, match_starts[1:]):
        if current < previous + config.table.nminutes_execution:
            raise ValueError(
                "Match execution intervals overlap for the head referee"
            )

    for round_no in (1, 2):
        current = table_events[table_events["RoundNo"] == round_no]
        following = table_events[table_events["RoundNo"] == round_no + 1]
        current_end = max(
            _minutes(row.Time) + int(row.Duration)
            for row in current.itertuples(index=False)
        )
        following_start = min(_minutes(value) for value in following["Time"])
        if following_start < current_end + config.table.match_break_duration:
            raise ValueError(f"Insufficient table break after Round {round_no}")

    judging = competitive[competitive["EventName"].isin(["Project", "Design"])]
    if not (judging["Duration"] == config.judging.nminutes_judging).all():
        raise ValueError("A judging appointment has the wrong duration")
    for (_, room), room_events in judging.groupby(["EventName", "Room"]):
        ordered = list(room_events.sort_values("Time").itertuples(index=False))
        for appointment_index, (previous, current) in enumerate(
            zip(ordered, ordered[1:]),
            start=1,
        ):
            required_turnover = config.judging.nminutes_between_judging
            if appointment_index % config.judging.nteams_per_judging_sprint == 0:
                required_turnover += config.judging.extra_sprint_break
            gap = _minutes(current.Time) - (
                _minutes(previous.Time) + int(previous.Duration)
            )
            if gap < required_turnover:
                raise ValueError(
                    f"Insufficient judging turnover in {room} after appointment {appointment_index}"
                )

    for room, room_events in events.groupby("Room"):
        ordered = room_events.sort_values("Time")
        previous_end = -1
        for row in ordered.itertuples(index=False):
            start = _minutes(row.Time)
            # Break rows may be informational markers inside lunch; competitive
            # events and lunch themselves must still reserve the resource.
            if row.EventName == "Break":
                continue
            if start < previous_end:
                raise ValueError(f"Resource overlap in {room} at {row.Time}")
            previous_end = start + int(row.Duration)

    lunch_start = tournament.optimization_result.lunch_start if tournament.optimization_result else parse_time(config.day.lunch_start)
    lunch_end = lunch_start + config.day.nminutes_lunch
    for row in competitive.itertuples(index=False):
        start = _minutes(row.Time)
        end = start + int(row.Duration)
        if start < lunch_end and end > lunch_start:
            raise ValueError(f"{row.EventName} in {row.Room} overlaps lunch")

    if tournament.optimization_result is not None:
        result = tournament.optimization_result
        opening_end = result.opening_start + config.day.opening_ceremony_duration
        first_match = min(_minutes(value) for value in table_events["Time"])
        if first_match != result.match_start or first_match < opening_end:
            raise ValueError("The first match does not respect the configured match start")
        if min(_minutes(value) for value in judging["Time"]) != result.judging_start:
            raise ValueError("Judging does not respect the configured judging start")
        if result.judging_start < opening_end:
            raise ValueError("Judging starts before the opening ceremony ends")
        competitive_finish = max(
            _minutes(row.Time) + int(row.Duration)
            for row in competitive.itertuples(index=False)
        )
        judging_finish = max(
            _minutes(row.Time) + int(row.Duration)
            for row in judging.itertuples(index=False)
        )
        if result.closing_start < competitive_finish:
            raise ValueError("Closing starts before competitive events finish")
        if result.closing_start < judging_finish + config.day.deliberation_duration:
            raise ValueError("Closing starts before judging deliberation can finish")
        if config.day.venue_closing_time is not None:
            if (
                result.closing_start + config.day.closing_ceremony_duration
                > parse_time(config.day.venue_closing_time)
            ):
                raise ValueError("Closing ceremony ends after the venue closes")

    if minimum_gap == 10**9:
        raise ValueError("No team gaps were found")
    return ValidationReport(minimum_gap, limiting_team, limiting_events)


def _event_label(event_name: str, round_no: int) -> str:
    return f"Table Round {round_no}" if event_name == "Table" else event_name

