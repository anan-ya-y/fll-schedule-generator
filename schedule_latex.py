from __future__ import annotations

from pathlib import Path

import pandas as pd

from schedule import DUMMY_TEAM_NO, Tournament
from utils import TimeUtils


def create_fllt(
    tournament: Tournament,
    output_folder: str | Path,
    date_str: str = "1/1/25",
) -> Path:
    """Create the exact nine-column FLLTournament import CSV used on main."""
    events = tournament.events.copy()
    events = events[events["EventName"].isin(["Table", "Project", "Design"])]
    events = events[events["Team"] != DUMMY_TEAM_NO]
    events.loc[events["EventName"] == "Design", "EventName"] = "Robot"

    events["Date"] = date_str
    events["Begin Time"] = events["Time"].apply(lambda value: value.strftime("%H:%M"))
    events["End Time"] = events.apply(
        lambda row: TimeUtils.add_times(row["Time"], int(row["Duration"])).strftime("%H:%M"),
        axis=1,
    )
    events["Type"] = events["EventName"]
    events["Round"] = events["RoundNo"].apply(lambda value: max(1, int(value)))
    events["Description"] = events.apply(
        lambda row: (
            f"Table Round {int(row['RoundNo'])}"
            if row["EventName"] == "Table"
            else f"{row['EventName']} Judging"
        ),
        axis=1,
    )
    events["Team #"] = events["Team"]
    events["Team Name"] = events["TeamName"]
    columns = [
        "Date",
        "Begin Time",
        "End Time",
        "Type",
        "Round",
        "Description",
        "Room",
        "Team #",
        "Team Name",
    ]
    destination = Path(output_folder) / "fllt_schedule.csv"
    events[columns].sort_values(["Begin Time", "Room"]).to_csv(destination, index=False)
    print(f"Finished. Saved to file: {destination}")
    return destination


def _create_doc(landscape: bool = False):
    try:
        from pylatex import Document, Package
        from pylatex.utils import NoEscape
    except ImportError as error:
        raise RuntimeError(
            "PyLaTeX is required for PDF schedules; install requirements.txt"
        ) from error

    options = ["a4paper", "margin=1cm", "landscape" if landscape else "portrait"]
    document = Document()
    document.packages.append(Package("geometry", options=options))
    document.packages.append(Package("xcolor", options="table"))
    document.append(NoEscape(r"\sffamily"))
    document.append(NoEscape(r"\def\arraystretch{1.5}"))
    return document


def _bold(value: object):
    from pylatex.utils import NoEscape

    return NoEscape(r"\textbf{" + str(value) + "}")


def create_team_schedule(tournament: Tournament, output_folder: str | Path) -> Path:
    """Create the legacy one-row-per-team schedule PDF."""
    from pylatex import Tabular
    from pylatex.utils import NoEscape

    document = _create_doc(landscape=True)
    document.append(NoEscape(r"\sffamily"))
    document.append(NoEscape(r"\def\arraystretch{1.5}"))
    document.append(NoEscape(r"\rowcolors{2}{gray!0}{gray!10}"))

    day = tournament.config.day
    opening_start = day.start_time.strftime("%I:%M %p")
    opening_end = TimeUtils.add_times(
        day.start_time,
        day.opening_ceremony_duration,
    ).strftime("%I:%M %p")
    has_lunch = (tournament.events["EventName"] == "Lunch").any()
    lunch_start = day.lunch_start.strftime("%I:%M %p")
    lunch_end = TimeUtils.add_times(
        day.lunch_start,
        day.nminutes_lunch,
    ).strftime("%I:%M %p")
    closing_start = day.closing_ceremony_time.strftime("%I:%M %p")

    with document.create(Tabular("|rl|cc|cc|cc|cc|cc|")) as table:
        table.add_hline()
        table.add_row(
            tuple(
                _bold(value)
                for value in (
                    r"Team \#",
                    "Team Name",
                    "Round 1",
                    r"Table \#",
                    "Round 2",
                    r"Table \#",
                    "Round 3",
                    r"Table \#",
                    "Project",
                    r"Room \#",
                    "Robot Design",
                    r"Room \#",
                )
            )
        )
        table.add_hline()
        team_numbers = sorted(
            int(value)
            for value in tournament.events["Team"].unique()
            if int(value) > 0 and int(value) != DUMMY_TEAM_NO
        )
        for team_number in team_numbers:
            team_events = tournament.get_events_by_team().get_group(team_number)
            display = {
                "Project": ("XX:XX", "Room X"),
                "Design": ("XX:XX", "Room X"),
                "Round 1": ("XX:XX", "Table X"),
                "Round 2": ("XX:XX", "Table X"),
                "Round 3": ("XX:XX", "Table X"),
            }
            for event in team_events.itertuples():
                key = event.EventName if event.RoundNo == 0 else f"Round {event.RoundNo}"
                if key in display:
                    display[key] = (event.Time.strftime("%I:%M %p"), event.Room)
            table.add_row(
                (
                    team_number,
                    tournament.config.team.teamnos_to_names[team_number],
                    display["Round 1"][0],
                    display["Round 1"][1],
                    display["Round 2"][0],
                    display["Round 2"][1],
                    display["Round 3"][0],
                    display["Round 3"][1],
                    display["Project"][0],
                    display["Project"][1],
                    display["Design"][0],
                    display["Design"][1],
                )
            )
            table.add_hline()

    document.append(f"\n\nOpening Ceremony: {opening_start} - {opening_end}")
    if has_lunch:
        document.append(f"\nLunch: {lunch_start} - {lunch_end}")
    document.append(f"\nClosing Ceremony: {closing_start}\n\n")
    document.append(NoEscape(r"\vspace{0.2in}"))
    destination = Path(output_folder) / "team_schedule"
    document.generate_pdf(str(destination), clean_tex=False, silent=True)
    pdf_path = destination.with_suffix(".pdf")
    print(f"Finished. Saved to file: {pdf_path}")
    return pdf_path


def create_judging_schedule(tournament: Tournament, output_folder: str | Path) -> Path:
    """Create the judging-room matrix, supporting unsynchronized room times."""
    from pylatex import Tabular
    from pylatex.utils import NoEscape

    document = _create_doc(landscape=True)
    document.append(NoEscape(r"\large"))
    document.append(NoEscape(r"\sffamily"))
    document.append(NoEscape(r"\def\arraystretch{1.5}"))
    document.append(NoEscape(r"\rowcolors{2}{gray!0}{gray!10}"))
    events = tournament.events
    project_events = events[events["EventName"] == "Project"]
    design_events = events[events["EventName"] == "Design"]
    judging_events = pd.concat([project_events, design_events])
    all_rooms = sorted(judging_events["Room"].unique().tolist())
    project_rooms = set(project_events["Room"].unique())
    room_events = events[events["Room"].isin(all_rooms)]
    times = sorted(room_events["Time"].unique().tolist())

    with document.create(Tabular("|c" * (1 + len(all_rooms)) + "|")) as table:
        table.add_hline()
        table.add_row(
            tuple(
                [_bold("Time")]
                + [
                    _bold(f"{room} ({'P' if room in project_rooms else 'D'})")
                    for room in all_rooms
                ]
            )
        )
        table.add_hline()
        for start in times:
            at_time = room_events[room_events["Time"] == start]
            cells = []
            for room in all_rooms:
                selected = at_time[at_time["Room"] == room]
                if selected.empty:
                    cells.append("")
                    continue
                event = selected.iloc[0]
                if event.Team > 0:
                    cells.append(f"{event.Team}: {event.TeamName}")
                else:
                    cells.append(str(event.TeamName).upper())
            table.add_row(tuple([start.strftime("%I:%M %p")] + cells))
            table.add_hline()

    destination = Path(output_folder) / "judging_schedule"
    document.generate_pdf(str(destination), clean_tex=False, silent=True)
    pdf_path = destination.with_suffix(".pdf")
    print(f"Finished. Saved to file: {pdf_path}")
    return pdf_path


def create_room_schedule(tournament: Tournament, output_folder: str | Path) -> Path:
    """Create one portrait page per judging room."""
    from pylatex import Tabular
    from pylatex.utils import NoEscape

    document = _create_doc(landscape=False)
    document.append(NoEscape(r"\Huge"))
    document.append(NoEscape(r"\rowcolors{2}{gray!0}{gray!10}"))
    events = tournament.events
    project_events = events[events["EventName"] == "Project"]
    design_events = events[events["EventName"] == "Design"]
    judging_events = pd.concat([project_events, design_events])
    rooms = judging_events["Room"].drop_duplicates().tolist()
    project_rooms = set(project_events["Room"].unique())

    for room_index, room in enumerate(rooms):
        selected = events[events["Room"] == room].sort_values("Time", kind="stable")
        document.append(NoEscape(r"\vspace*{0.1in}"))
        document.append(_bold(f"{room} ({'Project' if room in project_rooms else 'Design'})"))
        document.append(NoEscape(r"\newline"))
        document.append(NoEscape(r"\vspace{0.1in}"))
        with document.create(Tabular("|c|c|c|")) as table:
            table.add_hline()
            table.add_row((_bold("Time"), _bold(r"Team \#"), _bold("Team Name")))
            table.add_hline()
            for event in selected.itertuples():
                table.add_row(
                    (
                        event.Time.strftime("%I:%M %p"),
                        event.Team if event.Team > 0 else "",
                        event.TeamName if event.Team > 0 else str(event.TeamName).upper(),
                    )
                )
                table.add_hline()
        if room_index != len(rooms) - 1:
            document.append(NoEscape(r"\newpage"))

    destination = Path(output_folder) / "room_schedule"
    document.generate_pdf(str(destination), clean_tex=False, silent=True)
    pdf_path = destination.with_suffix(".pdf")
    print(f"Finished. Saved to file: {pdf_path}")
    return pdf_path


def _paired_table_rows(tournament: Tournament):
    """Yield table-room events as configured physical pairs at each time."""
    table_names = tournament.table_names
    table_events = tournament.events[
        tournament.events["Room"].isin(table_names)
    ]
    for start in sorted(table_events["Time"].unique().tolist()):
        time_events = table_events[table_events["Time"] == start]
        for pair_index in range(0, len(table_names), 2):
            pair_names = table_names[pair_index : pair_index + 2]
            selected = time_events[time_events["Room"].isin(pair_names)]
            if selected.empty:
                continue
            if len(selected) != 2 or set(selected["Room"]) != set(pair_names):
                raise ValueError(
                    f"Expected one event on each of {pair_names} at {start}, "
                    f"found {len(selected)}"
                )
            yield (
                start,
                selected[selected["Room"] == pair_names[0]].iloc[0],
                selected[selected["Room"] == pair_names[1]].iloc[0],
            )


def create_ref_schedule(tournament: Tournament, output_folder: str | Path) -> Path:
    """Create the referee schedule PDF, one row per physical table pair."""
    from pylatex import LongTable
    from pylatex.utils import NoEscape

    document = _create_doc(landscape=True)
    document.append(NoEscape(r"\large"))
    document.append(NoEscape(r"\sffamily"))
    document.append(NoEscape(r"\def\arraystretch{1.5}"))
    document.append(NoEscape(r"\rowcolors{2}{gray!0}{gray!10}"))
    with document.create(LongTable("|c|c|l|l|p{2.5in}|r|r|")) as table:
        table.add_hline()
        table.add_row(
            tuple(
                _bold(value)
                for value in (
                    "Time",
                    "Rnd",
                    "Table No.",
                    "Team 1",
                    "Notes",
                    "Team 2",
                    "Table No.",
                )
            )
        )
        table.add_hline()
        for start, first, second in _paired_table_rows(tournament):
            first_display = (
                f"{first.Team}: {first.TeamName}"
                if first.Team > 0
                else str(first.TeamName).upper()
            )
            second_display = (
                f"{second.Team}: {second.TeamName}"
                if second.Team > 0
                else str(second.TeamName).upper()
            )
            table.add_row(
                (
                    start.strftime("%I:%M %p"),
                    first.RoundNo,
                    first.Room,
                    first_display,
                    "   ",
                    second_display,
                    second.Room,
                )
            )
            table.add_hline()

    destination = Path(output_folder) / "ref_schedule"
    document.generate_pdf(str(destination), clean_tex=False, silent=True)
    pdf_path = destination.with_suffix(".pdf")
    print(f"Finished. Saved to file: {pdf_path}")
    return pdf_path


def create_emcee_schedule(tournament: Tournament, output_folder: str | Path) -> Path:
    """Create the emcee PDF, one row per physical table pair."""
    from pylatex import LongTable
    from pylatex.utils import NoEscape

    def bold(value: object):
        return NoEscape(r"\textbf{" + str(value) + "}")

    document = _create_doc(landscape=True)
    document.append(NoEscape(r"\large"))
    document.append(NoEscape(r"\sffamily"))
    document.append(NoEscape(r"\def\arraystretch{1.5}"))
    document.append(NoEscape(r"\rowcolors{2}{gray!0}{gray!10}"))

    with document.create(LongTable("|c|c|l|l|p{2.5in}|r|r|")) as table:
        table.add_hline()
        table.add_row(
            tuple(
                bold(value)
                for value in (
                    "Time",
                    "Rnd",
                    "Table No.",
                    "Team 1",
                    "Notes",
                    "Team 2",
                    "Table No.",
                )
            )
        )
        table.add_hline()
        for start, first, second in _paired_table_rows(tournament):
            first_display = (
                f"{first.Team}: {first.TeamName}"
                if first.Team > 0
                else str(first.TeamName).upper()
            )
            second_display = (
                f"{second.Team}: {second.TeamName}"
                if second.Team > 0
                else str(second.TeamName).upper()
            )
            first_note = "" if pd.isna(first["Note"]) else str(first["Note"])
            second_note = "" if pd.isna(second["Note"]) else str(second["Note"])
            table.add_row(
                (
                    start.strftime("%I:%M %p"),
                    first.RoundNo,
                    first.Room,
                    first_display,
                    NoEscape(f"\\tiny {first_note}\\hfill {second_note}"),
                    second_display,
                    second.Room,
                )
            )
            table.add_hline()

    destination = Path(output_folder) / "emcee_schedule"
    document.generate_pdf(str(destination), clean_tex=False, silent=True)
    pdf_path = destination.with_suffix(".pdf")
    print(f"Finished. Saved to file: {pdf_path}")
    return pdf_path

