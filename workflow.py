from __future__ import annotations

from dataclasses import dataclass, field
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
    warnings: list[str] = field(default_factory=list)


@dataclass
class TemplateRenderResult:
    tournament: Tournament
    validation: ValidationReport
    files: list[Path]
    warnings: list[str] = field(default_factory=list)


@dataclass
class AnonymousTemplateResult:
    optimization: OptimizationResult
    files: list[Path]


def _create_pdf_printouts(
    tournament: Tournament,
    output: Path,
    files: list[Path],
    warnings: list[str],
) -> None:
    renderers = (
        create_emcee_schedule,
        create_judging_schedule,
        create_ref_schedule,
        create_team_schedule,
        create_room_schedule,
    )
    for renderer in renderers:
        try:
            files.append(renderer(tournament, output))
        except Exception as error:
            warnings.append(
                "PDF schedule printouts were skipped because the LaTeX toolchain "
                f"could not compile them: {error}"
            )
            break


def generate_anonymous_template(
    config: Config,
    output_folder: str | Path,
) -> AnonymousTemplateResult:
    """Run only the optimizer and save its anonymous, reusable template."""
    config.validate()
    output = Path(output_folder)
    output.mkdir(parents=True, exist_ok=True)
    generated_config_path = output / "config_generated.json"
    config.to_json(generated_config_path)
    optimization = optimize(config)
    template_path = output / (
        "tournament_schedule_template_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".csv"
    )
    optimization.events.to_csv(template_path, index=False)
    metrics_path = output / "optimization_metrics.json"
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(optimization.metrics(), handle, indent=4)
    return AnonymousTemplateResult(
        optimization=optimization,
        files=[generated_config_path, template_path, metrics_path],
    )


def generate_schedule(
    config: Config,
    tournament_details: dict[str, Any],
    output_folder: str | Path,
    tournament_date: str,
    generate_pdfs: bool = True,
    details_base_directory: str | Path | None = None,
) -> WorkflowResult:
    """Run optimization, validation, and every requested legacy export."""
    config.validate()
    Tournament.room_names_from_details(config, tournament_details)

    output = Path(output_folder)
    output.mkdir(parents=True, exist_ok=True)
    generated_config_path = output / "config_generated.json"
    config.to_json(generated_config_path)
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
    tournament = Tournament.from_optimization(
        optimization,
        team_list,
        tournament_details,
    )
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

    files = [generated_config_path, template_path, normalized_path, metrics_path]
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
    warnings: list[str] = []
    if generate_pdfs:
        _create_pdf_printouts(tournament, output, files, warnings)
    return WorkflowResult(tournament, optimization, validation, files, warnings)


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
    table_diversity_weight: int | None = None,
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
    if table_diversity_weight is not None:
        config.solver.table_diversity_weight = table_diversity_weight
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
    tournament_details_path: str | Path,
    output_folder: str | Path,
    tournament_date: str | None = None,
    generate_pdfs: bool = True,
    team_list_csv: str | Path | None = None,
) -> TemplateRenderResult:
    """Fill a solved template with tournament details without running a solver."""
    output = Path(output_folder)
    output.mkdir(parents=True, exist_ok=True)
    details_path = Path(tournament_details_path)
    with details_path.open(encoding="utf-8") as handle:
        tournament_details = json.load(handle)
    if team_list_csv is not None:
        team_list = Path(team_list_csv)
    else:
        team_list = Path(tournament_details["teamlist"])
        if not team_list.is_absolute() and not team_list.exists():
            team_list = details_path.parent / team_list
    tournament = Tournament.from_template(
        template_csv,
        team_list,
        tournament_details,
    )
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
    warnings: list[str] = []
    if generate_pdfs:
        _create_pdf_printouts(tournament, output, files, warnings)
    return TemplateRenderResult(tournament, validation, files, warnings)
