from __future__ import annotations

from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest

import pandas as pd

# The Linux optimizer test environment intentionally omits Tk.  These tests cover
# the GUI's data/validation layer without constructing a window; lightweight base
# classes are enough to import that layer.  Windows builds use the real stdlib Tk.
try:
    import tkinter  # noqa: F401
except ModuleNotFoundError:
    class _Widget:
        pass

    tkinter_stub = ModuleType("tkinter")
    tkinter_stub.Tk = _Widget
    tkinter_stub.Misc = _Widget
    ttk_stub = ModuleType("tkinter.ttk")
    ttk_stub.Frame = _Widget
    filedialog_stub = ModuleType("tkinter.filedialog")
    messagebox_stub = ModuleType("tkinter.messagebox")
    simpledialog_stub = ModuleType("tkinter.simpledialog")
    simpledialog_stub.Dialog = _Widget
    tkinter_stub.filedialog = filedialog_stub
    tkinter_stub.messagebox = messagebox_stub
    tkinter_stub.simpledialog = simpledialog_stub
    tkinter_stub.ttk = ttk_stub
    sys.modules.update(
        {
            "tkinter": tkinter_stub,
            "tkinter.ttk": ttk_stub,
            "tkinter.filedialog": filedialog_stub,
            "tkinter.messagebox": messagebox_stub,
            "tkinter.simpledialog": simpledialog_stub,
        }
    )

from config import Config
from scheduler_gui import (
    ScheduleRequest,
    build_config,
    run_request,
    save_request_inputs,
    validate_teams,
    validate_tournament_date,
)


def form_values() -> dict[str, str]:
    return {
        "project_rooms": "Project A, Project B",
        "design_rooms": "Design A, Design B",
        "table_names": "Red Table, Blue Table",
        "opening_start": "08:00",
        "opening_duration": "20",
        "judging_start": "08:20",
        "matches_start": "10:00",
        "lunch_start": "12:00",
        "lunch_duration": "30",
        "closing_start": "15:30",
        "closing_latest": "18:00",
        "deliberation_duration": "0",
        "minimum_gap": "15",
        "round_1_duration": "10",
        "later_round_duration": "8",
        "match_break": "10",
        "execution_duration": "5",
        "judging_duration": "10",
        "judging_gap": "10",
        "sprint_size": "3",
        "sprint_break": "5",
        "solver_limit": "30",
        "finish_allowance": "0",
        "objective_mode": "lexicographic",
        "finish_weight": "10",
        "separation_weight": "5",
        "gap_weight": "1",
    }


class GuiSupportTests(unittest.TestCase):
    def test_build_config_maps_form_values(self) -> None:
        config = build_config(form_values())
        self.assertEqual(config.tournament.njudging_rooms, 2)
        self.assertEqual(config.tournament.ntables, 2)
        self.assertEqual(config.table.nminutes_execution, 5)
        self.assertEqual(config.day.judging_start_time, "08:20")
        self.assertEqual(config.team.time_between_events, 15)

    def test_mismatched_room_counts_are_rejected(self) -> None:
        values = form_values()
        values["design_rooms"] = "Design A"
        with self.assertRaisesRegex(ValueError, "same number"):
            build_config(values)

    def test_team_validation_normalizes_optional_notes(self) -> None:
        teams = validate_teams(
            pd.DataFrame(
                [
                    {"Team #": "101", "Team Name": " Alpha ", "Distance": "5"},
                    {"Team #": "202", "Team Name": "Beta", "Distance": "10"},
                ]
            )
        )
        self.assertEqual(list(teams.columns), ["Team #", "Team Name", "Distance", "Note"])
        self.assertEqual(teams.iloc[0]["Team Name"], "Alpha")
        self.assertEqual(teams.iloc[0]["Note"], "")

    def test_duplicate_team_numbers_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_teams([(1, "A", 0, ""), (1, "B", 0, "")])

    def test_odd_table_count_is_rejected_in_the_form(self) -> None:
        values = form_values()
        values["table_names"] = "Red, Blue, Green"
        with self.assertRaisesRegex(ValueError, "even number"):
            build_config(values)

    def test_date_is_normalized(self) -> None:
        self.assertEqual(validate_tournament_date("01/02/2027"), "1/2/2027")

    def test_saved_setup_is_portable_and_handles_odd_team_count(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            teams = validate_teams(
                [(101, "Alpha", 1, ""), (202, "Beta", 2, ""), (303, "Gamma", 3, "")]
            )
            request = ScheduleRequest(
                config=build_config(form_values(), Config()),
                teams=teams,
                table_rooms=["Red Table", "Blue Table"],
                project_rooms=["Project A", "Project B"],
                design_rooms=["Design A", "Design B"],
                input_directory=root / "inputs",
                output_directory=root / "output",
                tournament_date="1/2/2027",
                generate_pdfs=False,
            )
            details = save_request_inputs(request)
            self.assertEqual(details["teamlist"], "teamlist.csv")
            self.assertEqual(details["table_rooms"], ["Red Table", "Blue Table"])
            self.assertEqual(request.config.effective_nteams, 4)
            self.assertTrue((root / "inputs" / "config.json").is_file())
            self.assertTrue((root / "inputs" / "teamlist.csv").is_file())
            self.assertTrue((root / "inputs" / "gui_settings.json").is_file())

    def test_gui_request_runs_optimizer_and_creates_primary_outputs(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            teams = validate_teams(
                [
                    (101, "Alpha", 1, ""),
                    (202, "Beta", 2, ""),
                    (303, "Gamma", 3, ""),
                    (404, "Delta", 4, ""),
                ]
            )
            config = build_config(form_values())
            config.solver.max_time_seconds = 10
            request = ScheduleRequest(
                config=config,
                teams=teams,
                table_rooms=["Red Table", "Blue Table"],
                project_rooms=["Project A", "Project B"],
                design_rooms=["Design A", "Design B"],
                input_directory=root / "inputs",
                output_directory=root / "output",
                tournament_date="1/2/2027",
                generate_pdfs=False,
            )
            result = run_request(request)
            self.assertGreaterEqual(result.validation.minimum_gap, 15)
            for filename in (
                "config_generated.json",
                "fllt_schedule.csv",
                "all_rooms_schedule.html",
                "stats.txt",
                "tournament_schedule.csv",
            ):
                self.assertTrue((root / "output" / filename).is_file(), filename)


if __name__ == "__main__":
    unittest.main()
