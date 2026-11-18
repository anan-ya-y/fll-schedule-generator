from __future__ import annotations

import argparse
from workflow import load_and_generate


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimize an FLL tournament schedule")
    parser.add_argument("--config", help="Path to configuration JSON")
    parser.add_argument(
        "--tournament_details",
        required=True,
        help="JSON containing teamlist and table/project/design room names",
    )
    parser.add_argument("--output_folder", default="output/")
    parser.add_argument("--tournament_date", required=True, help="FLLT date, e.g. 1/31/2026")
    parser.add_argument(
        "--skip_pdf",
        action="store_true",
        help="Create data outputs without invoking LaTeX",
    )
    parser.add_argument("--solver_time_limit", type=float)
    parser.add_argument("--finish_allowance", type=int)
    parser.add_argument(
        "--objective_mode",
        choices=("lexicographic", "weighted"),
        help="Use strict priority stages or one tunable weighted objective",
    )
    parser.add_argument("--overall_finish_weight", type=int)
    parser.add_argument("--judging_separation_weight", type=int)
    parser.add_argument("--table_diversity_weight", type=int)
    parser.add_argument("--minimum_gap_weight", type=int)
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    result = load_and_generate(
        args.config,
        args.tournament_details,
        args.output_folder,
        args.tournament_date,
        generate_pdfs=not args.skip_pdf,
        solver_time_limit=args.solver_time_limit,
        finish_allowance=args.finish_allowance,
        objective_mode=args.objective_mode,
        overall_finish_weight=args.overall_finish_weight,
        judging_separation_weight=args.judging_separation_weight,
        table_diversity_weight=args.table_diversity_weight,
        minimum_gap_weight=args.minimum_gap_weight,
    )

    print()
    print("GENERATED LEGACY SCHEDULE FILES:")
    print(" - fllt_schedule.csv")
    print(" - all_rooms_schedule.html")
    print(" - stats.txt")
    if not args.skip_pdf:
        print(" - emcee_schedule.pdf")
        print(" - judging_schedule.pdf")
        print(" - ref_schedule.pdf")
        print(" - team_schedule.pdf")
        print(" - room_schedule.pdf")
    print()
    print(f"Minimum team gap: {result.validation.minimum_gap} minutes")
    print(
        f"Limiting team: {result.validation.limiting_team} "
        f"({result.validation.limiting_events[0]} -> {result.validation.limiting_events[1]})"
    )
    for warning in result.warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()

