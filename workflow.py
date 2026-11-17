from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from config import Config
from optimizer import OptimizationResult, optimize
from schedule import Tournament
from schedule_html import create_all_rooms_schedule
from statistics_report import create_statistics_report
from schedule_latex import (
    create_emcee_schedule,
    create_fllt,
    create_judging_schedule,
    create_ref_schedule,
    create_room_schedule,
    create_team_schedule,
)
from validation import ValidationReport, validate_tournament


@dataclass
class WorkflowResult:
    tournament: Tournament
    optimization: OptimizationResult
    validation: ValidationReport
    files: list[Path]


@dataclass
class TemplateRenderResult:
    tournament: Tournament
    validation: ValidationReport
    files: list[Path]


def generate_schedule(
    config: Config,
    tournament_details: dict[str, Any],
    output_folder: str | Path,
    tournament_date: str,
    generate_pdfs: bool = True,
    details_base_directory: str | Path | None = None,
) -> WorkflowResult:
    """Run optimization, validation, and every requested legacy export."""
    project_rooms = list(tournament_details["project_rooms"])
    design_rooms = list(tournament_details["design_rooms"])
    if len(project_rooms) != len(design_rooms):
        raise ValueError("Project and Design must have the same number of rooms")
    config.tournament.njudging_rooms = len(project_rooms)
    config.tournament.project_room_names = project_rooms
    config.tournament.design_room_names = design_rooms
    config.validate()

    output = Path(output_folder)
    output.mkdir(parents=True, exist_ok=True)
    config.to_json("config_generated.json")
    optimization = optimize(config)
    template_path = output / (
        "tournament_schedule_template_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".csv"
    )
    optimization.events.to_csv(template_path, index=False)

    team_list = Path(tournament_details["teamlist"])
    if not team_list.is_absolute() and not team_list.exists() and details_base_directory:
        team_list = Path(details_base_directory) / team_list
    tournament = Tournament.from_optimization(optimization, team_list)
    validation = validate_tournament(tournament)

    normalized_path = output / "tournament_schedule.csv"
    tournament.save_schedule_csv(normalized_path)
    metrics_path = output / "optimization_metrics.json"
    metrics = optimization.metrics()
    metrics["validated_minimum_gap"] = validation.minimum_gap
    metrics["limiting_team"] = validation.limiting_team
    metrics["limiting_events"] = list(validation.limiting_events)
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=4)

    files = [template_path, normalized_path, metrics_path]
    files.append(create_fllt(tournament, output, tournament_date))
    files.append(create_all_rooms_schedule(tournament, output))
    files.append(
        create_statistics_report(
            tournament,
            optimization,
            validation,
            output,
        )
    )
    if generate_pdfs:
        files.extend(
            [
                create_emcee_schedule(tournament, output),
                create_judging_schedule(tournament, output),
                create_ref_schedule(tournament, output),
                create_team_schedule(tournament, output),
                create_room_schedule(tournament, output),
            ]
        )
    return WorkflowResult(tournament, optimization, validation, files)


def load_and_generate(
    config_path: str | Path | None,
    tournament_details_path: str | Path,
    output_folder: str | Path,
    tournament_date: str,
    generate_pdfs: bool = True,
    solver_time_limit: float | None = None,
    finish_allowance: int | None = None,
    objective_mode: str | None = None,
    overall_finish_weight: int | None = None,
    judging_separation_weight: int | None = None,
    minimum_gap_weight: int | None = None,
) -> WorkflowResult:
    config = Config.from_json(config_path) if config_path else Config()
    details_path = Path(tournament_details_path)
    with details_path.open(encoding="utf-8") as handle:
        details = json.load(handle)
    if solver_time_limit is not None:
        config.solver.max_time_seconds = solver_time_limit
    if finish_allowance is not None:
        config.solver.finish_allowance = finish_allowance
    if objective_mode is not None:
        config.solver.objective_mode = objective_mode
    if overall_finish_weight is not None:
        config.solver.overall_finish_weight = overall_finish_weight
    if judging_separation_weight is not None:
        config.solver.judging_separation_weight = judging_separation_weight
    if minimum_gap_weight is not None:
        config.solver.minimum_gap_weight = minimum_gap_weight
    return generate_schedule(
        config,
        details,
        output_folder,
        tournament_date,
        generate_pdfs=generate_pdfs,
        details_base_directory=details_path.parent,
    )


def render_solved_template(
    template_csv: str | Path,
    team_list_csv: str | Path,
    output_folder: str | Path,
    tournament_date: str | None = None,
    generate_pdfs: bool = True,
) -> TemplateRenderResult:
    """Attach teams and render outputs without building or solving a model."""
    output = Path(output_folder)
    output.mkdir(parents=True, exist_ok=True)
    tournament = Tournament.from_template(template_csv, team_list_csv)
    validation = validate_tournament(tournament)

    normalized_path = output / "tournament_schedule.csv"
    tournament.save_schedule_csv(normalized_path)
    files = [normalized_path]
    files.append(create_all_rooms_schedule(tournament, output))
    files.append(
        create_statistics_report(
            tournament,
            None,
            validation,
            output,
        )
    )
    if tournament_date:
        files.append(create_fllt(tournament, output, tournament_date))
    if generate_pdfs:
        files.extend(
            [
                create_emcee_schedule(tournament, output),
                create_judging_schedule(tournament, output),
                create_ref_schedule(tournament, output),
                create_team_schedule(tournament, output),
                create_room_schedule(tournament, output),
            ]
        )
    return TemplateRenderResult(tournament, validation, files)
