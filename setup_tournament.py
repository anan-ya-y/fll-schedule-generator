from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from config import Config, minute_to_time, parse_time
from workflow import generate_schedule


def ask_text(prompt: str, default: str) -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def ask_int(prompt: str, default: int) -> int:
    while True:
        try:
            return int(ask_text(prompt, str(default)))
        except ValueError:
            print("Please enter a whole number.")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def ask_rooms(label: str, count: int) -> list[str]:
    default = ", ".join(f"{label} {index + 1}" for index in range(count))
    while True:
        rooms = [value.strip() for value in ask_text(f"{label} room names", default).split(",")]
        if len(rooms) == count and all(rooms):
            return rooms
        print(f"Please provide exactly {count} comma-separated room names.")


def enter_teams(number_of_teams: int) -> pd.DataFrame:
    print("\nEnter each team. Notes may be left blank.")
    rows = []
    for index in range(number_of_teams):
        print(f"\nTeam {index + 1} of {number_of_teams}")
        team_number = ask_int("  Team number", index + 1)
        team_name = ask_text("  Team name", f"Team {team_number}")
        distance = ask_text("  Travel distance", "0")
        note = input("  Optional emcee note: ").strip()
        rows.append(
            {
                "Team #": team_number,
                "Team Name": team_name,
                "Distance": float(distance),
                "Note": note,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    print("FLL Schedule Setup")
    print("This wizard creates the three input files and can run the optimizer immediately.\n")
    input_directory = Path(ask_text("Input folder", "tournament_input")).resolve()
    input_directory.mkdir(parents=True, exist_ok=True)
    output_directory = Path(
        ask_text("Output folder", str(input_directory / "output"))
    ).resolve()

    config = Config()
    number_of_teams = ask_int("Number of real teams", config.tournament.nteams)
    config.tournament.nteams = number_of_teams
    if number_of_teams % 2:
        print("An odd number of teams requires a filler opponent.")
        if not ask_yes_no("Add the standard dummy team 99999?"):
            raise SystemExit("An even team count or dummy team is required.")
        config.tournament.odd_team_policy = "dummy"

    room_count = ask_int("Rooms per judging type", config.tournament.njudging_rooms)
    project_rooms = ask_rooms("Project", room_count)
    design_rooms = ask_rooms("Design", room_count)
    config.tournament.njudging_rooms = room_count
    config.tournament.project_room_names = project_rooms
    config.tournament.design_room_names = design_rooms
    config.day.start_time = ask_text("Opening ceremony start (HH:MM)", config.day.start_time)
    config.day.opening_ceremony_duration = ask_int(
        "Opening ceremony duration in minutes",
        config.day.opening_ceremony_duration,
    )
    default_judging_start = minute_to_time(
        parse_time(config.day.start_time)
        + config.day.opening_ceremony_duration
    ).strftime("%H:%M")
    config.day.judging_start_time = ask_text(
        "First judging appointment (HH:MM)",
        default_judging_start,
    )
    config.day.matches_start_time = ask_text(
        "First match start (HH:MM)",
        config.day.matches_start_time,
    )
    config.day.lunch_start = ask_text("Lunch start (HH:MM)", config.day.lunch_start)
    config.day.nminutes_lunch = ask_int("Lunch duration in minutes", config.day.nminutes_lunch)
    config.day.closing_ceremony_time = ask_text(
        "Earliest closing ceremony start (HH:MM)",
        config.day.closing_ceremony_time,
    )
    config.day.closing_ceremony_time_latest = ask_text(
        "Latest closing ceremony start (HH:MM)",
        config.day.closing_ceremony_time_latest or config.day.closing_ceremony_time,
    )
    config.team.time_between_events = ask_int(
        "Required minimum team gap in minutes",
        config.team.time_between_events,
    )
    config.solver.max_time_seconds = float(
        ask_text("Solver time limit per stage in seconds", str(config.solver.max_time_seconds))
    )
    config.solver.finish_allowance = ask_int(
        "Minutes of finish-time flexibility when maximizing gaps",
        config.solver.finish_allowance,
    )

    existing_team_list = input("Existing team-list CSV (leave blank to enter teams now): ").strip()
    if existing_team_list:
        team_list_path = Path(existing_team_list).resolve()
        if not team_list_path.is_file():
            raise SystemExit(f"Team list does not exist: {team_list_path}")
    else:
        team_list_path = input_directory / "teamlist.csv"
        enter_teams(number_of_teams).to_csv(team_list_path, index=False)

    config_path = input_directory / "config.json"
    details_path = input_directory / "tournament_details.json"
    config.validate()
    config.to_json(config_path)
    details = {
        "teamlist": str(team_list_path),
        "project_rooms": project_rooms,
        "design_rooms": design_rooms,
    }
    with details_path.open("w", encoding="utf-8") as handle:
        json.dump(details, handle, indent=4)

    tournament_date = ask_text("Tournament date for FLLT", "1/1/2027")
    print("\nInputs created:")
    print(f"  {config_path}")
    print(f"  {details_path}")
    print(f"  {team_list_path}")
    print("\nRun again later with:")
    print(
        "  venv/bin/python schedule_generator.py"
        f" --config \"{config_path}\""
        f" --tournament_details \"{details_path}\""
        f" --output_folder \"{output_directory}\""
        f" --tournament_date {tournament_date}"
    )

    if ask_yes_no("Run the optimizer and create all six legacy outputs now?"):
        result = generate_schedule(
            config,
            details,
            output_directory,
            tournament_date,
            generate_pdfs=True,
        )
        print(f"\nDone. Minimum team gap: {result.validation.minimum_gap} minutes")
        print(f"Outputs: {output_directory}")


if __name__ == "__main__":
    main()

