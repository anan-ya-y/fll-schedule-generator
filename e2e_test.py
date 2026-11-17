from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from config import Config
from workflow import generate_schedule


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a complete four-team smoke test")
    parser.add_argument("--output", default="e2e_output")
    parser.add_argument("--skip-pdf", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = arguments()
    output = Path(args.output).resolve()
    inputs = output / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)

    config = Config()
    config.tournament.nteams = 4
    config.tournament.project_room_names = ["Project A", "Project B"]
    config.tournament.design_room_names = ["Design A", "Design B"]
    config.day.start_time = "08:00"
    config.day.matches_start_time = "11:30"
    config.day.lunch_start = "13:00"
    config.day.nminutes_lunch = 30
    config.day.closing_ceremony_time = "17:00"
    config.day.closing_ceremony_time_latest = "18:00"
    config.team.time_between_events = 10
    config.solver.max_time_seconds = 30
    config.solver.num_search_workers = 1

    team_list_path = inputs / "teamlist.csv"
    pd.DataFrame(
        [
            {"Team #": 101, "Team Name": "Alpha", "Distance": 5, "Note": ""},
            {"Team #": 202, "Team Name": "Beta", "Distance": 15, "Note": "Late arrival"},
            {"Team #": 303, "Team Name": "Gamma", "Distance": 25, "Note": ""},
            {"Team #": 404, "Team Name": "Delta", "Distance": 35, "Note": ""},
        ]
    ).to_csv(team_list_path, index=False)
    config.to_json(inputs / "config.json")
    details = {
        "teamlist": str(team_list_path),
        "project_rooms": config.tournament.project_room_names,
        "design_rooms": config.tournament.design_room_names,
    }
    with (inputs / "tournament_details.json").open("w", encoding="utf-8") as handle:
        json.dump(details, handle, indent=4)

    result = generate_schedule(
        config,
        details,
        output,
        "1/31/2027",
        generate_pdfs=not args.skip_pdf,
    )
    required = {
        "fllt_schedule.csv",
        "tournament_schedule.csv",
        "optimization_metrics.json",
        "all_rooms_schedule.html",
        "stats.txt",
    }
    if not args.skip_pdf:
        required.update(
            {
                "emcee_schedule.pdf",
                "judging_schedule.pdf",
                "ref_schedule.pdf",
                "team_schedule.pdf",
                "room_schedule.pdf",
            }
        )
    missing = sorted(name for name in required if not (output / name).is_file())
    empty = sorted(
        name
        for name in required
        if (output / name).is_file() and (output / name).stat().st_size == 0
    )
    if missing or empty:
        raise SystemExit(f"E2E verification failed; missing={missing}, empty={empty}")

    print("\nEND-TO-END TEST PASSED")
    print(f"Minimum team gap: {result.validation.minimum_gap} minutes")
    print(f"Verified {len(required)} primary output files in {output}")


if __name__ == "__main__":
    main()
