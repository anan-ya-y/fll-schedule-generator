from __future__ import annotations

import csv
from datetime import time
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from config import Config
from schedule import FINAL_EVENT_COLUMNS, Tournament
from schedule_latex import (
    create_emcee_schedule,
    create_fllt,
    create_judging_schedule,
    create_ref_schedule,
    create_room_schedule,
    create_team_schedule,
)


class OutputContractTests(unittest.TestCase):
    def setUp(self) -> None:
        config = Config()
        config.tournament.nteams = 2
        rows = []
        for round_no, start in ((1, time(10, 0)), (2, time(10, 30)), (3, time(11, 0))):
            for team, room in ((1, "Table 1"), (2, "Table 2")):
                rows.append(
                    {
                        "Time": start,
                        "EventName": "Table",
                        "RoundNo": round_no,
                        "Room": room,
                        "Duration": 10 if round_no == 1 else 8,
                        "Team": team,
                    }
                )
        for team, minute in ((1, 0), (2, 40)):
            rows.extend(
                [
                    {
                        "Time": time(8, minute),
                        "EventName": "Project",
                        "RoundNo": 0,
                        "Room": "P1",
                        "Duration": 30,
                        "Team": team,
                    },
                    {
                        "Time": time(9, minute),
                        "EventName": "Design",
                        "RoundNo": 0,
                        "Room": "D1",
                        "Duration": 30,
                        "Team": team,
                    },
                ]
            )
        rows.append(
            {
                "Time": time(12, 0),
                "EventName": "Lunch",
                "RoundNo": 0,
                "Room": "Table 1",
                "Duration": 60,
                "Team": -2,
            }
        )
        anonymous = pd.DataFrame(rows)
        result = SimpleNamespace(
            config=config,
            events=anonymous,
            opening_start=8 * 60,
            match_start=10 * 60,
            lunch_start=12 * 60,
            closing_start=15 * 60 + 30,
        )
        teams = pd.DataFrame(
            [
                {"Team #": 101, "Team Name": "Alpha", "Distance": 1},
                {"Team #": 202, "Team Name": "Beta", "Distance": 2},
            ]
        )
        self.tournament = Tournament.from_optimization(
            result,
            teams,
            {
                "teamlist": "teamlist.csv",
                "table_rooms": ["Table 1", "Table 2"],
                "project_rooms": ["P1", "P2"],
                "design_rooms": ["D1", "D2"],
            },
        )

    def test_final_dataframe_shape(self) -> None:
        self.assertEqual(list(self.tournament.events), FINAL_EVENT_COLUMNS)
        lunch = self.tournament.events[self.tournament.events["EventName"] == "Lunch"].iloc[0]
        self.assertEqual(lunch["Team"], -2)
        self.assertEqual(lunch["TeamName"], "Lunch")

    def test_fllt_columns_and_filters(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            destination = create_fllt(self.tournament, directory, "1/31/2026")
            with destination.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 10)
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
        self.assertEqual({row["Type"] for row in rows}, {"Table", "Project", "Robot"})

    def test_all_pdf_renderers_use_lualatex(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            with patch("pylatex.Document.generate_pdf") as generate_pdf:
                with patch("schedule_latex._paired_table_rows", return_value=iter(())):
                    for renderer in (
                        create_emcee_schedule,
                        create_judging_schedule,
                        create_ref_schedule,
                        create_team_schedule,
                        create_room_schedule,
                    ):
                        renderer(self.tournament, directory)

        self.assertEqual(generate_pdf.call_count, 5)
        for call in generate_pdf.call_args_list:
            self.assertEqual(call.kwargs["compiler"], "lualatex")


if __name__ == "__main__":
    unittest.main()
