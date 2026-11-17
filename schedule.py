from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from config import Config, minute_to_time

if TYPE_CHECKING:
    from optimizer.solve import OptimizationResult


DUMMY_TEAM_NO = 99999
FINAL_EVENT_COLUMNS = [
    "Time",
    "EventName",
    "RoundNo",
    "Room",
    "Duration",
    "Team",
    "Team ID",
    "TeamName",
    "Note",
]


class Tournament:
    """Legacy-compatible public schedule object backed by a pandas DataFrame."""

    def __init__(
        self,
        config: Config,
        events: pd.DataFrame,
        team_list: pd.DataFrame,
        optimization_result: OptimizationResult | None = None,
    ) -> None:
        self.config = config
        self.optimization_result = optimization_result
        self.nteams = config.effective_nteams
        self.teamid_keys = list(range(1, self.nteams + 1))
        self.config.tournament.nproject_rooms = self.config.tournament.njudging_rooms
        self.config.tournament.ndesign_rooms = self.config.tournament.njudging_rooms
        if optimization_result is not None:
            self.config.day.start_time = minute_to_time(optimization_result.opening_start)
            self.config.day.matches_start_time = minute_to_time(
                optimization_result.match_start
            )
            self.config.day.lunch_start = minute_to_time(optimization_result.lunch_start)
            self.config.day.closing_ceremony_time = minute_to_time(
                optimization_result.closing_start
            )
            self.config.day.opening_ceremony_end_time = minute_to_time(
                optimization_result.opening_start
                + self.config.day.opening_ceremony_duration
            )
            self.config.day.lunch_end = minute_to_time(
                optimization_result.lunch_start + self.config.day.nminutes_lunch
            )
        self.config.team.team_list = team_list
        self.config.team.teamnos_to_names = {
            int(row["Team #"]): str(row["Team Name"]).strip()
            for _, row in team_list.iterrows()
        }
        self.events = self._assign_actual_teams(events.copy(), team_list)

    @classmethod
    def from_optimization(
        cls,
        result: OptimizationResult,
        team_list: str | Path | pd.DataFrame,
    ) -> "Tournament":
        frame = pd.read_csv(team_list) if not isinstance(team_list, pd.DataFrame) else team_list.copy()
        normalized = cls._normalize_team_list(result.config, frame)
        return cls(result.config, result.events, normalized, result)

    @classmethod
    def from_template(
        cls,
        template_csv: str | Path,
        team_list: str | Path | pd.DataFrame,
    ) -> "Tournament":
        """Attach real teams to an already-solved anonymous schedule template."""
        events = pd.read_csv(template_csv)
        required = {"Time", "EventName", "RoundNo", "Room", "Duration", "Team"}
        missing = sorted(required - set(events.columns))
        if missing:
            raise ValueError(f"Template is missing columns: {', '.join(missing)}")
        events["Time"] = pd.to_datetime(events["Time"], format="mixed").dt.time
        if "Team ID" in events.columns:
            events["Team"] = events["Team ID"]
        events = events[["Time", "EventName", "RoundNo", "Room", "Duration", "Team"]]
        events["RoundNo"] = events["RoundNo"].astype(int)
        events["Duration"] = events["Duration"].astype(int)
        events["Team"] = events["Team"].astype(int)

        team_ids = sorted(int(value) for value in events["Team"].unique() if int(value) > 0)
        if team_ids != list(range(1, len(team_ids) + 1)):
            raise ValueError("Template team IDs must be consecutive integers starting at 1")
        config = cls._infer_config(events, len(team_ids))

        frame = pd.read_csv(team_list) if not isinstance(team_list, pd.DataFrame) else team_list.copy()
        if "Distance" not in frame:
            frame["Distance"] = range(len(frame))
        if len(frame) == len(team_ids) - 1:
            config.tournament.odd_team_policy = "dummy"
        normalized = cls._normalize_team_list(config, frame)
        return cls(config, events, normalized, None)

    @staticmethod
    def _infer_config(events: pd.DataFrame, nteams: int) -> Config:
        config = Config()
        config.tournament.nteams = nteams
        table_events = events[events["EventName"] == "Table"]
        project_events = events[events["EventName"] == "Project"]
        design_events = events[events["EventName"] == "Design"]
        table_names = table_events["Room"].drop_duplicates().astype(str).tolist()
        project_rooms = project_events["Room"].drop_duplicates().astype(str).tolist()
        design_rooms = design_events["Room"].drop_duplicates().astype(str).tolist()
        if len(table_names) != 2:
            raise ValueError("Template rendering requires exactly two table rooms")
        if not project_rooms or len(project_rooms) != len(design_rooms):
            raise ValueError("Template must have equal nonzero Project and Design room counts")
        config.tournament.table_names = table_names
        config.tournament.njudging_rooms = len(project_rooms)
        config.tournament.project_room_names = project_rooms
        config.tournament.design_room_names = design_rooms
        config.tournament.ntable_rounds = int(table_events["RoundNo"].max())

        round_one = table_events[table_events["RoundNo"] == 1]
        later_rounds = table_events[table_events["RoundNo"] > 1]
        config.table.nminutes_table_rnd1 = int(round_one["Duration"].mode().iloc[0])
        config.table.nminutes_table_allrounds = int(later_rounds["Duration"].mode().iloc[0])
        config.table.match_break_duration = 0
        config.judging.nminutes_judging = int(
            pd.concat([project_events, design_events])["Duration"].mode().iloc[0]
        )
        config.judging.nminutes_between_judging = 0
        config.judging.extra_sprint_break = 0

        competitive = events[events["EventName"].isin(["Table", "Project", "Design"])]
        earliest_judging = min(
            value.hour * 60 + value.minute
            for value in pd.concat([project_events, design_events])["Time"]
        )
        first_match = min(value.hour * 60 + value.minute for value in table_events["Time"])
        latest_end = max(
            row.Time.hour * 60 + row.Time.minute + int(row.Duration)
            for row in competitive.itertuples(index=False)
        )
        opening_start = max(
            0,
            earliest_judging
            - config.day.opening_ceremony_duration
        )
        config.day.start_time = minute_to_time(opening_start)
        config.day.matches_start_time = minute_to_time(first_match)
        config.day.closing_ceremony_time = minute_to_time(latest_end)
        config.day.closing_ceremony_time_latest = None
        config.day.opening_ceremony_end_time = minute_to_time(
            opening_start + config.day.opening_ceremony_duration
        )

        lunch_events = events[events["EventName"] == "Lunch"]
        if not lunch_events.empty:
            lunch = lunch_events.iloc[0]
            config.day.lunch_start = lunch["Time"]
            config.day.nminutes_lunch = int(lunch["Duration"])
        else:
            config.day.lunch_start = minute_to_time(12 * 60)
            config.day.nminutes_lunch = 0
        config.day.lunch_start_latest = None
        config.day.lunch_end = minute_to_time(
            config.day.lunch_start.hour * 60
            + config.day.lunch_start.minute
            + config.day.nminutes_lunch
        )
        config.day.venue_closing_time = None
        config.day.deliberation_duration = 0
        config.team.time_between_events = 0
        config.validate()
        return config

    @staticmethod
    def _normalize_team_list(config: Config, team_list: pd.DataFrame) -> pd.DataFrame:
        required = {"Team #", "Team Name", "Distance"}
        missing = sorted(required - set(team_list.columns))
        if missing:
            raise ValueError(f"Team list is missing columns: {', '.join(missing)}")
        team_list = team_list.copy()
        team_list["Team #"] = team_list["Team #"].astype(int)
        team_list["Team Name"] = team_list["Team Name"].astype(str).str.strip()
        team_list["Distance"] = team_list["Distance"].astype(float)
        if team_list["Team #"].duplicated().any():
            raise ValueError("Team numbers must be unique")
        if "Note" not in team_list:
            team_list["Note"] = ""
        team_list["Note"] = team_list["Note"].fillna("").astype(str)

        expected = config.effective_nteams
        if len(team_list) == expected:
            return team_list.reset_index(drop=True)
        if (
            len(team_list) == expected - 1
            and config.tournament.odd_team_policy == "dummy"
        ):
            dummy = pd.DataFrame(
                [
                    {
                        "Team #": DUMMY_TEAM_NO,
                        "Team Name": "FILLER TEAM",
                        "Distance": 0.0,
                        "Note": "",
                    }
                ]
            )
            return pd.concat([team_list, dummy], ignore_index=True)
        raise ValueError(
            f"The optimizer has {expected} team identities, but the team list has {len(team_list)} rows"
        )

    def _assign_actual_teams(
        self,
        events: pd.DataFrame,
        team_list: pd.DataFrame,
    ) -> pd.DataFrame:
        competitive = events[events["EventName"].isin(["Table", "Project", "Design"])]
        earliest_judging: list[tuple[Any, int]] = []
        for team_id in self.teamid_keys:
            judging = competitive[
                (competitive["Team"] == team_id)
                & (competitive["EventName"].isin(["Project", "Design"]))
            ]
            if judging.empty:
                raise ValueError(f"Template team {team_id} has no judging appointment")
            earliest_judging.append((judging["Time"].min(), team_id))
        earliest_judging.sort()

        actual_teams = sorted(
            (
                float(row["Distance"]),
                int(row["Team #"]),
                str(row["Team Name"]),
                str(row.get("Note", "")),
            )
            for _, row in team_list.iterrows()
        )
        events["Team ID"] = events["Team"].astype(int)
        events["TeamName"] = pd.NA
        events["Note"] = pd.NA
        for (_, team_id), (_, team_number, team_name, note) in zip(
            earliest_judging,
            actual_teams,
            strict=True,
        ):
            selected = events["Team ID"] == team_id
            events.loc[selected, "Team"] = team_number
            events.loc[selected, "TeamName"] = team_name
            events.loc[selected, "Note"] = note

        no_team = events["Team ID"] == -2
        events.loc[no_team, "Team"] = -2
        events.loc[no_team, "TeamName"] = events.loc[no_team, "EventName"]
        events["Team"] = events["Team"].astype(int)
        events["Team ID"] = events["Team ID"].astype(int)
        return events[FINAL_EVENT_COLUMNS].sort_values("Time", kind="stable")

    def get_events_by_team(self):
        self.events = self.events.sort_values("Time", kind="stable")
        return self.events.groupby("Team")

    def get_team_events_interval_list(self, teamno: int):
        events = self.get_events_by_team().get_group(teamno)
        return list(events[["Time", "Duration"]].itertuples(index=False, name=None))

    def save_schedule_csv(self, filename: str | Path) -> None:
        self.events.to_csv(filename, index=False)

