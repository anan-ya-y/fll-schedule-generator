from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from config import Config
from schedule import FINAL_EVENT_COLUMNS, Tournament
from schedule_html import create_all_rooms_schedule
from schedule_latex import _paired_table_rows, create_fllt
from statistics_report import create_statistics_report
from validation import validate_tournament

try:
    from optimizer import optimize
except ModuleNotFoundError as error:
    if error.name is None or not error.name.startswith("ortools"):
        raise
    optimize = None


def small_config() -> Config:
    config = Config()
    config.tournament.nteams = 4
    config.tournament.project_room_names = ["Project A", "Project B"]
    config.tournament.design_room_names = ["Design A", "Design B"]
    config.day.start_time = "08:00"
    config.day.judging_start_time = "08:30"
    config.day.matches_start_time = "11:30"
    config.day.lunch_start = "13:00"
    config.day.nminutes_lunch = 30
    config.day.closing_ceremony_time = "17:00"
    config.team.time_between_events = 10
    config.solver.max_time_seconds = 30
    config.solver.num_search_workers = 1
    config.validate()
    return config


def team_list() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Team #": 101, "Team Name": "Alpha", "Distance": 5, "Note": ""},
            {"Team #": 202, "Team Name": "Beta", "Distance": 15, "Note": "Late arrival"},
            {"Team #": 303, "Team Name": "Gamma", "Distance": 25, "Note": ""},
            {"Team #": 404, "Team Name": "Delta", "Distance": 35, "Note": ""},
        ]
    )


@unittest.skipIf(optimize is None, "OR-Tools is not installed")
class OptimizerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = optimize(small_config())
        cls.tournament = Tournament.from_optimization(cls.result, team_list())

    def test_legacy_dataframe_contract(self) -> None:
        self.assertEqual(list(self.tournament.events.columns), FINAL_EVENT_COLUMNS)
        self.assertFalse((self.tournament.events["Team"] == -1).any())

    def test_schedule_validates(self) -> None:
        report = validate_tournament(self.tournament)
        self.assertGreaterEqual(report.minimum_gap, 10)
        self.assertIn("maximum_judging_table_separation", self.result.stages)
        self.assertLessEqual(self.result.judging_finish, self.result.finish)
        self.assertEqual(
            self.result.judging_table_separation,
            self.result.table_finish - self.result.judging_finish,
        )

    def test_opening_precedes_judging_and_matches(self) -> None:
        opening_end = (
            self.result.opening_start
            + self.result.config.day.opening_ceremony_duration
        )
        self.assertEqual(self.result.opening_start, 8 * 60)
        self.assertEqual(self.result.judging_start, 8 * 60 + 30)
        self.assertGreaterEqual(self.result.judging_start, opening_end)
        self.assertGreaterEqual(self.result.match_start, opening_end)

    def test_weighted_objective_mode(self) -> None:
        config = small_config()
        config.solver.objective_mode = "weighted"
        config.solver.max_time_seconds = 10
        result = optimize(config)
        self.assertIn("weighted_objective", result.stages)
        self.assertGreaterEqual(result.minimum_gap, config.team.time_between_events)

    def test_matches_have_two_synchronized_table_positions(self) -> None:
        table_events = self.tournament.events[
            self.tournament.events["EventName"] == "Table"
        ]
        for _, match in table_events.groupby(["RoundNo", "Time"]):
            self.assertEqual(len(match), 2)
            self.assertEqual(set(match["Room"]), {"Table 1", "Table 2"})

    def test_every_team_uses_both_tables(self) -> None:
        table_events = self.tournament.events[
            self.tournament.events["EventName"] == "Table"
        ]
        for _, events in table_events.groupby("Team ID"):
            self.assertEqual(set(events["Room"]), {"Table 1", "Table 2"})

    def test_fllt_export_contract(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            destination = create_fllt(self.tournament, directory, "1/31/2026")
            with destination.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                list(rows[0]),
                [
                    "Date",
                    "Begin Time",
                    "End Time",
                    "Type",
                    "Round",
                    "Description",
                    "Room",
                    "Team #",
                    "Team Name",
                ],
            )
            self.assertEqual(len(rows), 20)
            self.assertNotIn("Design", {row["Type"] for row in rows})
            self.assertNotIn("Break", {row["Type"] for row in rows})

    def test_all_rooms_visualization_uses_team_colors_and_zoom(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            destination = create_all_rooms_schedule(self.tournament, directory)
            content = destination.read_text(encoding="utf-8")
        self.assertIn('id="zoom" type="range"', content)
        self.assertIn("Small", content)
        self.assertIn("Large", content)
        self.assertIn("--team-light", content)
        self.assertIn("minmax(290px,1.35fr)", content)
        self.assertIn("101: Alpha", content)
        self.assertNotIn("px/minute", content)
        self.assertNotIn("Team color gradient", content)
        self.assertNotIn("Breaks and lunch", content)

    def test_statistics_report_has_gap_and_room_sections(self) -> None:
        report = validate_tournament(self.tournament)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            destination = create_statistics_report(
                self.tournament,
                self.result,
                report,
                directory,
            )
            content = destination.read_text(encoding="utf-8")
        self.assertIn("Shortest gap:", content)
        self.assertIn("Longest gap:", content)
        self.assertIn("Population standard deviation:", content)
        self.assertIn("ROOM DAY LENGTHS", content)
        self.assertIn("Table 1", content)

    def test_solved_template_can_attach_teams_without_config(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            directory = Path(directory)
            template = directory / "template.csv"
            teams = directory / "teams.csv"
            self.result.events.to_csv(template, index=False)
            team_list()[["Team #", "Team Name", "Note"]].to_csv(teams, index=False)
            rendered = Tournament.from_template(template, teams)
            report = validate_tournament(rendered)
        self.assertEqual(len(rendered.events[rendered.events["EventName"] == "Table"]), 12)
        self.assertEqual(set(rendered.events.loc[rendered.events["Team"] > 0, "Team"]), {101, 202, 303, 404})
        self.assertGreaterEqual(report.minimum_gap, 10)


class ConfigurationTests(unittest.TestCase):
    def test_table_count_must_form_complete_pairs(self) -> None:
        config = Config()
        config.tournament.ntables = 3
        config.tournament.table_names = ["Table 1", "Table 2", "Table 3"]
        with self.assertRaisesRegex(ValueError, "even number"):
            config.validate()

    def test_judging_start_must_follow_opening(self) -> None:
        config = Config()
        config.day.start_time = "08:00"
        config.day.opening_ceremony_duration = 20
        config.day.judging_start_time = "08:15"
        with self.assertRaisesRegex(ValueError, "judging_start_time"):
            config.validate()

    def test_missing_judging_start_defaults_to_opening_end(self) -> None:
        config = Config()
        config.day.start_time = "08:00"
        config.day.opening_ceremony_duration = 20
        config.day.judging_start_time = None
        config.validate()
        self.assertEqual(config.judging_window, (8 * 60 + 20, 8 * 60 + 20))

    def test_matches_must_follow_opening(self) -> None:
        config = Config()
        config.day.start_time = "09:00"
        config.day.opening_ceremony_duration = 20
        config.day.matches_start_time = "09:15"
        with self.assertRaisesRegex(ValueError, "matches_start_time"):
            config.validate()

    def test_odd_team_count_requires_explicit_dummy_policy(self) -> None:
        config = Config()
        config.tournament.nteams = 5
        with self.assertRaisesRegex(ValueError, "must be even"):
            config.validate()
        config.tournament.odd_team_policy = "dummy"
        config.validate()
        self.assertEqual(config.effective_nteams, 6)


@unittest.skipIf(optimize is None, "OR-Tools is not installed")
class MultiTableOptimizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = small_config()
        config.tournament.ntables = 4
        config.tournament.table_names = [
            "Table 1",
            "Table 2",
            "Table 3",
            "Table 4",
        ]
        config.solver.max_time_seconds = 30
        cls.result = optimize(config)
        cls.tournament = Tournament.from_optimization(cls.result, team_list())

    def test_matches_use_only_configured_adjacent_pairs(self) -> None:
        table_events = self.tournament.events[
            self.tournament.events["EventName"] == "Table"
        ]
        allowed_pairs = {
            frozenset(("Table 1", "Table 2")),
            frozenset(("Table 3", "Table 4")),
        }
        used_pairs = set()
        for _, match in table_events.groupby(["RoundNo", "Time"]):
            pair = frozenset(match["Room"])
            self.assertIn(pair, allowed_pairs)
            used_pairs.add(pair)
        self.assertEqual(used_pairs, allowed_pairs)

    def test_scoring_can_overlap_but_executions_do_not(self) -> None:
        table_events = self.tournament.events[
            self.tournament.events["EventName"] == "Table"
        ]
        round_one_starts = sorted(
            value.hour * 60 + value.minute
            for value in table_events.loc[
                table_events["RoundNo"] == 1, "Time"
            ].unique()
        )
        self.assertEqual(
            round_one_starts[1] - round_one_starts[0],
            self.result.config.table.nminutes_execution,
        )
        self.assertLess(
            round_one_starts[1],
            round_one_starts[0]
            + self.result.config.table.nminutes_table_rnd1,
        )

    def test_multitable_schedule_validates_and_keeps_finish_objective(self) -> None:
        validate_tournament(self.tournament)
        self.assertIn("maximum_judging_table_separation", self.result.stages)
        self.assertEqual(
            self.result.judging_table_separation,
            self.result.table_finish - self.result.judging_finish,
        )

    def test_operational_print_rows_preserve_table_pairs(self) -> None:
        allowed_pairs = {
            frozenset(("Table 1", "Table 2")),
            frozenset(("Table 3", "Table 4")),
        }
        rows = list(_paired_table_rows(self.tournament))
        self.assertTrue(rows)
        for _, first, second in rows:
            self.assertIn(frozenset((first.Room, second.Room)), allowed_pairs)


if __name__ == "__main__":
    unittest.main()
