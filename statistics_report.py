from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import statistics

from optimizer.solve import OptimizationResult
from schedule import DUMMY_TEAM_NO, Tournament
from validation import ValidationReport


def _minutes(value) -> int:
    return value.hour * 60 + value.minute


def _clock(value: int) -> str:
    hour = (value // 60) % 24
    minute = value % 60
    suffix = "AM" if hour < 12 else "PM"
    return f"{hour % 12 or 12}:{minute:02d} {suffix}"


def _duration(value: float) -> str:
    rounded = int(round(value))
    hours, minutes = divmod(rounded, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h 0m"
    return f"{minutes}m"


def _event_label(event_name: str, round_no: int) -> str:
    return f"Table Round {round_no}" if event_name == "Table" else event_name


def _union_minutes(intervals: list[tuple[int, int]]) -> int:
    if not intervals:
        return 0
    merged = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return sum(end - start for start, end in merged)


@dataclass(frozen=True)
class GapRecord:
    minutes: int
    team: int
    first: str
    second: str


def create_statistics_report(
    tournament: Tournament,
    optimization: OptimizationResult | None,
    validation: ValidationReport,
    output_folder: str | Path,
) -> Path:
    """Write human-readable schedule and optimization statistics."""
    events = tournament.events
    competitive = events[events["EventName"].isin(["Table", "Project", "Design"])]
    team_numbers = sorted(
        int(value)
        for value in competitive["Team"].unique()
        if int(value) > 0 and int(value) != DUMMY_TEAM_NO
    )
    gaps: list[GapRecord] = []
    team_rows = []
    for team in team_numbers:
        selected = competitive[competitive["Team"] == team].sort_values("Time")
        records = list(selected.itertuples(index=False))
        team_gaps = []
        for first, second in zip(records, records[1:]):
            value = _minutes(second.Time) - (_minutes(first.Time) + int(first.Duration))
            gap = GapRecord(
                value,
                team,
                _event_label(first.EventName, int(first.RoundNo)),
                _event_label(second.EventName, int(second.RoundNo)),
            )
            gaps.append(gap)
            team_gaps.append(value)
        first_start = min(_minutes(row.Time) for row in records)
        last_end = max(_minutes(row.Time) + int(row.Duration) for row in records)
        activity = sum(int(row.Duration) for row in records)
        team_rows.append(
            {
                "team": team,
                "min": min(team_gaps),
                "max": max(team_gaps),
                "mean": statistics.fmean(team_gaps),
                "stdev": statistics.pstdev(team_gaps),
                "span": last_end - first_start,
                "activity": activity,
                "idle": last_end - first_start - activity,
            }
        )

    gap_values = [record.minutes for record in gaps]
    shortest = min(gaps, key=lambda record: record.minutes)
    longest = max(gaps, key=lambda record: record.minutes)
    earliest = min(_minutes(row.Time) for row in events.itertuples(index=False))
    latest = max(
        _minutes(row.Time) + int(row.Duration)
        for row in events.itertuples(index=False)
    )
    table_events = competitive[competitive["EventName"] == "Table"]
    matches = len(table_events) // 2
    opponent_pairs = {
        tuple(sorted(int(value) for value in group["Team"]))
        for _, group in table_events.groupby(["RoundNo", "Time"])
    }

    lines = [
        "FLL SCHEDULE OPTIMIZATION STATISTICS",
        "====================================",
        "",
        "OVERALL SCHEDULE",
        f"Teams: {len(team_numbers)}",
        f"Competitive events: {len(competitive)} team assignments",
        f"Matches: {matches}",
        f"Unique opponent pairs: {len(opponent_pairs)}",
        f"First scheduled room event: {_clock(earliest)}",
        f"Last scheduled room event ends: {_clock(latest)}",
        f"Overall room-event span: {_duration(latest - earliest)}",
        f"Validated minimum team gap: {_duration(validation.minimum_gap)}",
        "",
        "TEAM TRANSITION GAPS",
        f"Consecutive gaps measured: {len(gap_values)}",
        (
            f"Shortest gap: {_duration(shortest.minutes)} - Team {shortest.team}, "
            f"{shortest.first} to {shortest.second}"
        ),
        (
            f"Longest gap: {_duration(longest.minutes)} - Team {longest.team}, "
            f"{longest.first} to {longest.second}"
        ),
        f"Average gap: {_duration(statistics.fmean(gap_values))} ({statistics.fmean(gap_values):.2f} minutes)",
        f"Median gap: {_duration(statistics.median(gap_values))}",
        f"Population standard deviation: {statistics.pstdev(gap_values):.2f} minutes",
        "",
        "PER-TEAM GAP AND DAY SUMMARY",
        "Team   Min gap   Max gap   Avg gap   Std dev   Team span   Activity   Idle",
    ]
    for row in team_rows:
        lines.append(
            f"{row['team']:<6} "
            f"{_duration(row['min']):>9} "
            f"{_duration(row['max']):>9} "
            f"{_duration(row['mean']):>9} "
            f"{row['stdev']:>8.2f}m "
            f"{_duration(row['span']):>11} "
            f"{_duration(row['activity']):>10} "
            f"{_duration(row['idle']):>7}"
        )

    lines.extend(
        [
            "",
            "ROOM DAY LENGTHS",
            "Span is measured from the room's first event start to its last event end.",
            "Room                         First      Last       Span       Busy       Utilization  Events",
        ]
    )
    room_order = (
        tournament.table_names
        + tournament.project_room_names
        + tournament.design_room_names
    )
    for room in dict.fromkeys(room_order + events["Room"].tolist()):
        selected = events[events["Room"] == room]
        intervals = [
            (_minutes(row.Time), _minutes(row.Time) + int(row.Duration))
            for row in selected.itertuples(index=False)
        ]
        first = min(start for start, _ in intervals)
        last = max(end for _, end in intervals)
        span = last - first
        busy = _union_minutes(intervals)
        utilization = (busy / span * 100) if span else 0
        lines.append(
            f"{str(room):<28} {_clock(first):<10} {_clock(last):<10} "
            f"{_duration(span):<10} {_duration(busy):<10} {utilization:>9.1f}%  {len(selected):>6}"
        )

    lines.extend(["", "OPTIMIZATION"])
    if optimization is None:
        lines.append("Render-only mode: an existing solved template was used; no optimizer was run.")
    else:
        lines.append(f"Optimized minimum gap: {_duration(optimization.minimum_gap)}")
        lines.append(
            "Opening ceremony: "
            f"{_clock(optimization.opening_start)} - "
            f"{_clock(optimization.opening_start + optimization.config.day.opening_ceremony_duration)}"
        )
        lines.append(f"Judging starts: {_clock(optimization.judging_start)}")
        lines.append(f"Table matches start: {_clock(optimization.match_start)}")
        lines.append(f"Judging finishes: {_clock(optimization.judging_finish)}")
        lines.append(f"Table matches finish: {_clock(optimization.table_finish)}")
        lines.append(
            "Judging-to-table-finish separation: "
            f"{_duration(optimization.judging_table_separation)}"
        )
        lines.append(f"All competitive events finish: {_clock(optimization.finish)}")
        for name, stage in optimization.stages.items():
            label = name.replace("_", " ").title()
            objective = "n/a" if stage.objective is None else str(stage.objective)
            bound = "n/a" if stage.best_bound is None else f"{stage.best_bound:.2f}"
            lines.append(
                f"{label}: status={stage.status}, objective={objective}, "
                f"best bound={bound}, wall time={stage.wall_time_seconds:.3f}s"
            )

    destination = Path(output_folder) / "stats.txt"
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Finished. Saved to file: {destination}")
    return destination
