from __future__ import annotations

import argparse

from workflow import render_solved_template


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Attach a team list to a solved template and render schedules"
    )
    parser.add_argument("--template", required=True, help="Solved anonymous template CSV")
    parser.add_argument("--teams", required=True, help="Team-list CSV")
    parser.add_argument("--output", default="template_output", help="Output folder")
    parser.add_argument(
        "--tournament-date",
        help="Optional date for the FLLTournament CSV, e.g. 1/31/2027",
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Create normalized CSV, statistics, and HTML without PDFs",
    )
    return parser.parse_args()


def main() -> None:
    args = arguments()
    result = render_solved_template(
        args.template,
        args.teams,
        args.output,
        tournament_date=args.tournament_date,
        generate_pdfs=not args.skip_pdf,
    )
    print()
    print("TEMPLATE RENDER COMPLETE")
    print(f"Minimum team gap: {result.validation.minimum_gap} minutes")
    print(f"Files written: {len(result.files)}")
    for path in result.files:
        print(f" - {path}")


if __name__ == "__main__":
    main()
