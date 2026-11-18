from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import traceback
from typing import Any, Mapping, Sequence
import webbrowser

import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from config import Config, minute_to_time, parse_time
from workflow import WorkflowResult, generate_schedule


APP_NAME = "FLL Schedule Generator"
TEAM_COLUMNS = ("Team #", "Team Name", "Distance", "Note")


@dataclass
class ScheduleRequest:
    config: Config
    teams: pd.DataFrame
    table_rooms: list[str]
    project_rooms: list[str]
    design_rooms: list[str]
    input_directory: Path
    output_directory: Path
    tournament_date: str
    generate_pdfs: bool


def _integer(values: Mapping[str, str], key: str, label: str, minimum: int = 0) -> int:
    try:
        value = int(values[key].strip())
    except (KeyError, ValueError) as error:
        raise ValueError(f"{label} must be a whole number.") from error
    if value < minimum:
        raise ValueError(f"{label} must be at least {minimum}.")
    return value


def _number(values: Mapping[str, str], key: str, label: str, minimum: float = 0) -> float:
    try:
        value = float(values[key].strip())
    except (KeyError, ValueError) as error:
        raise ValueError(f"{label} must be a number.") from error
    if value < minimum:
        raise ValueError(f"{label} must be at least {minimum}.")
    return value


def _time(values: Mapping[str, str], key: str, label: str) -> str:
    value = values.get(key, "").strip()
    try:
        minutes = parse_time(value)
    except (ValueError, TypeError) as error:
        raise ValueError(f"{label} must use 24-hour HH:MM format.") from error
    if not 0 <= minutes < 24 * 60:
        raise ValueError(f"{label} must be a time between 00:00 and 23:59.")
    return minute_to_time(minutes).strftime("%H:%M")


def _room_names(value: str, label: str) -> list[str]:
    names = [name.strip() for name in value.split(",") if name.strip()]
    if not names:
        raise ValueError(f"Enter at least one {label} room.")
    if len(set(names)) != len(names):
        raise ValueError(f"{label.title()} room names must be unique.")
    return names


def build_config(values: Mapping[str, str], base: Config | None = None) -> Config:
    """Build and validate a Config from GUI-safe string values."""
    config = copy.deepcopy(base or Config())
    project_rooms = _room_names(values.get("project_rooms", ""), "Innovation Project")
    design_rooms = _room_names(values.get("design_rooms", ""), "Robot Design")
    if len(project_rooms) != len(design_rooms):
        raise ValueError("Innovation Project and Robot Design must have the same number of rooms.")

    config.tournament.njudging_rooms = len(project_rooms)
    table_names = _room_names(values.get("table_names", ""), "table")
    if len(table_names) < 2 or len(table_names) % 2:
        raise ValueError("Enter an even number of competition tables (2, 4, 6, …).")
    config.tournament.ntables = len(table_names)

    config.day.start_time = _time(values, "opening_start", "Opening start")
    config.day.opening_ceremony_duration = _integer(
        values, "opening_duration", "Opening duration"
    )
    config.day.judging_start_time = _time(values, "judging_start", "Judging start")
    config.day.matches_start_time = _time(values, "matches_start", "Matches start")
    config.day.lunch_start = _time(values, "lunch_start", "Lunch start")
    config.day.nminutes_lunch = _integer(values, "lunch_duration", "Lunch duration")
    config.day.closing_ceremony_time = _time(values, "closing_start", "Closing start")
    config.day.closing_ceremony_time_latest = _time(
        values, "closing_latest", "Latest closing start"
    )
    config.day.deliberation_duration = _integer(
        values, "deliberation_duration", "Deliberation duration"
    )

    config.team.time_between_events = _integer(
        values, "minimum_gap", "Minimum team gap"
    )
    config.table.nminutes_table_rnd1 = _integer(
        values, "round_1_duration", "Round 1 match duration", 1
    )
    config.table.nminutes_table_allrounds = _integer(
        values, "later_round_duration", "Later-round match duration", 1
    )
    config.table.match_break_duration = _integer(
        values, "match_break", "Match break duration"
    )
    config.table.nminutes_execution = _integer(
        values, "execution_duration", "Match execution duration", 1
    )
    config.judging.nminutes_judging = _integer(
        values, "judging_duration", "Judging duration", 1
    )
    config.judging.nminutes_between_judging = _integer(
        values, "judging_gap", "Time between judging appointments"
    )
    config.judging.nteams_per_judging_sprint = _integer(
        values, "sprint_size", "Teams per judging sprint", 1
    )
    config.judging.extra_sprint_break = _integer(
        values, "sprint_break", "Judging sprint break"
    )

    objective_mode = values.get("objective_mode", "lexicographic").strip()
    if objective_mode not in {"lexicographic", "weighted"}:
        raise ValueError("Objective mode must be lexicographic or weighted.")
    config.solver.objective_mode = objective_mode
    config.solver.max_time_seconds = _number(
        values, "solver_limit", "Solver time limit", 1
    )
    config.solver.finish_allowance = _integer(
        values, "finish_allowance", "Finish allowance"
    )
    config.solver.overall_finish_weight = _integer(
        values, "finish_weight", "Finish weight"
    )
    config.solver.judging_separation_weight = _integer(
        values, "separation_weight", "Judging separation weight"
    )
    config.solver.minimum_gap_weight = _integer(
        values, "gap_weight", "Minimum-gap weight"
    )
    return config


def validate_teams(rows: Sequence[Sequence[Any]] | pd.DataFrame) -> pd.DataFrame:
    """Normalize user-entered teams and return the exact optimizer CSV shape."""
    if isinstance(rows, pd.DataFrame):
        missing = [column for column in TEAM_COLUMNS[:3] if column not in rows.columns]
        if missing:
            raise ValueError("Team CSV is missing: " + ", ".join(missing))
        frame = rows.copy()
        if "Note" not in frame.columns:
            frame["Note"] = ""
        frame = frame[list(TEAM_COLUMNS)]
    else:
        frame = pd.DataFrame(list(rows), columns=TEAM_COLUMNS)

    if frame.empty:
        raise ValueError("Add or import at least one team.")
    try:
        team_numbers = pd.to_numeric(frame["Team #"], errors="raise")
        distances = pd.to_numeric(frame["Distance"], errors="raise")
    except (TypeError, ValueError) as error:
        raise ValueError("Team numbers and travel distances must be numeric.") from error
    if team_numbers.isna().any() or distances.isna().any():
        raise ValueError("Team numbers and travel distances cannot be blank.")
    if (team_numbers % 1 != 0).any():
        raise ValueError("Team numbers must be whole numbers.")
    if (distances < 0).any():
        raise ValueError("Travel distances cannot be negative.")
    if team_numbers.duplicated().any():
        duplicates = sorted({int(value) for value in team_numbers[team_numbers.duplicated(False)]})
        raise ValueError("Team numbers must be unique. Duplicates: " + ", ".join(map(str, duplicates)))

    names = frame["Team Name"].fillna("").astype(str).str.strip()
    if (names == "").any():
        raise ValueError("Every team needs a name.")
    normalized = pd.DataFrame(
        {
            "Team #": team_numbers.astype(int),
            "Team Name": names,
            "Distance": distances.astype(float),
            "Note": frame["Note"].fillna("").astype(str).str.strip(),
        }
    )
    return normalized


def validate_tournament_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value.strip(), "%m/%d/%Y")
    except ValueError as error:
        raise ValueError("Tournament date must use M/D/YYYY format.") from error
    return f"{parsed.month}/{parsed.day}/{parsed.year}"


def save_request_inputs(request: ScheduleRequest) -> dict[str, Any]:
    """Persist a portable setup folder and return workflow tournament details."""
    request.input_directory.mkdir(parents=True, exist_ok=True)
    request.output_directory.mkdir(parents=True, exist_ok=True)
    request.config.tournament.nteams = len(request.teams)
    expected = (
        ("competition tables", request.table_rooms, request.config.tournament.ntables),
        ("Innovation Project rooms", request.project_rooms, request.config.tournament.njudging_rooms),
        ("Robot Design rooms", request.design_rooms, request.config.tournament.njudging_rooms),
    )
    for label, names, count in expected:
        if len(names) != count:
            raise ValueError(f"Enter exactly {count} {label}.")
    all_room_names = request.table_rooms + request.project_rooms + request.design_rooms
    if len(set(all_room_names)) != len(all_room_names):
        raise ValueError("Room names must be unique across all room types.")
    request.config.validate()

    team_path = request.input_directory / "teamlist.csv"
    request.teams.to_csv(team_path, index=False)
    request.config.to_json(request.input_directory / "config.json")
    details = {
        "teamlist": "teamlist.csv",
        "table_rooms": request.table_rooms,
        "project_rooms": request.project_rooms,
        "design_rooms": request.design_rooms,
    }
    with (request.input_directory / "tournament_details.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(details, handle, indent=4)
    metadata = {
        "tournament_date": request.tournament_date,
        "output_directory": str(request.output_directory),
        "generate_pdfs": request.generate_pdfs,
    }
    with (request.input_directory / "gui_settings.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(metadata, handle, indent=4)
    return details


def run_request(request: ScheduleRequest) -> WorkflowResult:
    details = save_request_inputs(request)
    return generate_schedule(
        request.config,
        details,
        request.output_directory,
        request.tournament_date,
        generate_pdfs=request.generate_pdfs,
        details_base_directory=request.input_directory,
    )


def open_path(path: Path) -> None:
    path = path.resolve()
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.body = ttk.Frame(canvas, padding=(18, 14))
        window = canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        self.body.bind(
            "<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind(
            "<Configure>", lambda event: canvas.itemconfigure(window, width=event.width)
        )
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)


class TeamDialog(simpledialog.Dialog):
    def __init__(self, parent: tk.Misc, values: Sequence[str] | None = None) -> None:
        self.initial = list(values or ("", "", "0", ""))
        self.result: tuple[str, str, str, str] | None = None
        super().__init__(parent, title="Team")

    def body(self, master: tk.Misc) -> tk.Widget:
        self.entries: list[ttk.Entry] = []
        for row, (label, value) in enumerate(zip(TEAM_COLUMNS, self.initial)):
            ttk.Label(master, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=6)
            entry = ttk.Entry(master, width=38)
            entry.insert(0, value)
            entry.grid(row=row, column=1, sticky="ew", padx=6, pady=6)
            self.entries.append(entry)
        return self.entries[0]

    def validate(self) -> bool:
        values = tuple(entry.get().strip() for entry in self.entries)
        try:
            validate_teams([values])
        except ValueError as error:
            messagebox.showerror("Check team", str(error), parent=self)
            return False
        self.result = values  # type: ignore[assignment]
        return True


class SchedulerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1060x760")
        self.minsize(880, 650)
        self.base_config = Config()
        self.values: dict[str, tk.StringVar] = {}
        self.worker_messages: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.last_result: WorkflowResult | None = None
        self._build_style()
        self._build_menu()
        self._build_ui()
        self.new_setup()
        self.after(150, self._poll_worker)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        available = style.theme_names()
        if "vista" in available:
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#4b5563")
        style.configure("Section.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 9))
        style.configure("Status.TLabel", padding=(8, 4))

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New setup", command=self.new_setup, accelerator="Ctrl+N")
        file_menu.add_command(label="Open saved setup…", command=self.load_setup, accelerator="Ctrl+O")
        file_menu.add_command(label="Save setup", command=self.save_setup, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(
            label="About",
            command=lambda: messagebox.showinfo(
                "About",
                "FLL Schedule Generator\n\nBuilds optimized tournament schedules and printable operations files.",
                parent=self,
            ),
        )
        menu.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=menu)
        self.bind_all("<Control-n>", lambda _event: self.new_setup())
        self.bind_all("<Control-o>", lambda _event: self.load_setup())
        self.bind_all("<Control-s>", lambda _event: self.save_setup())

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(20, 14, 20, 10))
        header.pack(fill="x")
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Enter the tournament details, review the teams, and generate every operations file in one run.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=18)
        self.setup_tab = ttk.Frame(self.notebook, padding=16)
        self.teams_tab = ttk.Frame(self.notebook, padding=16)
        self.day_tab = ScrollableFrame(self.notebook)
        self.advanced_tab = ScrollableFrame(self.notebook)
        self.results_tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(self.setup_tab, text="1  Setup")
        self.notebook.add(self.teams_tab, text="2  Teams")
        self.notebook.add(self.day_tab, text="3  Schedule")
        self.notebook.add(self.advanced_tab, text="4  Advanced")
        self.notebook.add(self.results_tab, text="5  Results")
        self._build_setup_tab()
        self._build_teams_tab()
        self._build_day_tab()
        self._build_advanced_tab()
        self._build_results_tab()

        footer = ttk.Frame(self, padding=(18, 10, 18, 14))
        footer.pack(fill="x")
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel").pack(side="left")
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=180)
        self.progress.pack(side="left", padx=10)
        self.generate_button = ttk.Button(
            footer, text="Generate schedule", style="Primary.TButton", command=self.generate
        )
        self.generate_button.pack(side="right")

    def _var(self, key: str) -> tk.StringVar:
        variable = self.values.get(key)
        if variable is None:
            variable = tk.StringVar()
            self.values[key] = variable
        return variable

    def _entry_row(
        self,
        parent: tk.Misc,
        row: int,
        label: str,
        key: str,
        help_text: str = "",
        width: int = 28,
    ) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=7)
        entry = ttk.Entry(parent, textvariable=self._var(key), width=width)
        entry.grid(row=row, column=1, sticky="ew", pady=7)
        if help_text:
            ttk.Label(parent, text=help_text, style="Subtitle.TLabel").grid(
                row=row, column=2, sticky="w", padx=(12, 0), pady=7
            )
        return entry

    def _path_row(self, parent: tk.Misc, row: int, label: str, key: str) -> None:
        self._entry_row(parent, row, label, key, width=55)
        ttk.Button(parent, text="Browse…", command=lambda: self._browse_directory(key)).grid(
            row=row, column=2, sticky="w", padx=(12, 0), pady=7
        )

    def _build_setup_tab(self) -> None:
        self.setup_tab.columnconfigure(1, weight=1)
        ttk.Label(self.setup_tab, text="Tournament files", style="Section.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        self._entry_row(
            self.setup_tab, 1, "Tournament date", "tournament_date", "M/D/YYYY"
        )
        self._path_row(self.setup_tab, 2, "Setup folder", "input_directory")
        self._path_row(self.setup_tab, 3, "Results folder", "output_directory")
        ttk.Separator(self.setup_tab).grid(row=4, column=0, columnspan=3, sticky="ew", pady=16)
        ttk.Label(self.setup_tab, text="Rooms", style="Section.TLabel").grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        self._entry_row(
            self.setup_tab,
            6,
            "Innovation Project rooms",
            "project_rooms",
            "Comma-separated",
            45,
        )
        self._entry_row(
            self.setup_tab,
            7,
            "Robot Design rooms",
            "design_rooms",
            "Use the same number of rooms",
            45,
        )
        self._entry_row(
            self.setup_tab,
            8,
            "Competition tables",
            "table_names",
            "An even number; paired in order",
            45,
        )
        ttk.Separator(self.setup_tab).grid(row=9, column=0, columnspan=3, sticky="ew", pady=16)
        self.pdf_var = tk.BooleanVar()
        self.pdf_check = ttk.Checkbutton(
            self.setup_tab,
            text="Create the five printable PDF schedules",
            variable=self.pdf_var,
        )
        self.pdf_check.grid(row=10, column=0, columnspan=3, sticky="w")
        self.latex_note = ttk.Label(self.setup_tab, style="Subtitle.TLabel")
        self.latex_note.grid(row=11, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(
            self.setup_tab,
            text="Your setup is saved as reusable JSON and CSV files whenever a schedule is generated.",
            style="Subtitle.TLabel",
        ).grid(row=12, column=0, columnspan=3, sticky="w", pady=(20, 0))

    def _build_teams_tab(self) -> None:
        toolbar = ttk.Frame(self.teams_tab)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Import CSV…", command=self.import_teams).pack(side="left")
        ttk.Button(toolbar, text="Add team", command=self.add_team).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Edit", command=self.edit_team).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Remove", command=self.remove_teams).pack(side="left", padx=(8, 0))
        self.team_count_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self.team_count_var, style="Subtitle.TLabel").pack(side="right")
        table_frame = ttk.Frame(self.teams_tab)
        table_frame.pack(fill="both", expand=True)
        self.team_tree = ttk.Treeview(
            table_frame, columns=TEAM_COLUMNS, show="headings", selectmode="extended"
        )
        widths = (100, 260, 120, 360)
        for column, width in zip(TEAM_COLUMNS, widths):
            self.team_tree.heading(column, text=column)
            self.team_tree.column(column, width=width, minwidth=80)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.team_tree.yview)
        self.team_tree.configure(yscrollcommand=scrollbar.set)
        self.team_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.team_tree.bind("<Double-1>", lambda _event: self.edit_team())

    def _build_day_tab(self) -> None:
        body = self.day_tab.body
        body.columnconfigure(1, weight=1)
        ttk.Label(body, text="Event day", style="Section.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        rows = [
            ("Opening ceremony start", "opening_start", "24-hour HH:MM"),
            ("Opening ceremony duration", "opening_duration", "minutes"),
            ("First judging appointment", "judging_start", "24-hour HH:MM"),
            ("First table match", "matches_start", "24-hour HH:MM"),
            ("Lunch start", "lunch_start", "24-hour HH:MM"),
            ("Lunch duration", "lunch_duration", "minutes"),
            ("Earliest closing ceremony", "closing_start", "24-hour HH:MM"),
            ("Latest closing ceremony", "closing_latest", "24-hour HH:MM"),
            ("Deliberation after judging", "deliberation_duration", "minutes"),
            ("Required team gap", "minimum_gap", "minutes between events"),
        ]
        for row, (label, key, help_text) in enumerate(rows, start=1):
            self._entry_row(body, row, label, key, help_text)

    def _build_advanced_tab(self) -> None:
        body = self.advanced_tab.body
        body.columnconfigure(1, weight=1)
        ttk.Label(body, text="Event durations", style="Section.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        rows = [
            ("Match execution", "execution_duration", "minutes using the head referee"),
            ("Round 1 table occupancy", "round_1_duration", "execution plus scoring"),
            ("Rounds 2 and 3 table occupancy", "later_round_duration", "execution plus scoring"),
            ("Break between match rounds", "match_break", "minutes"),
            ("Judging appointment", "judging_duration", "minutes"),
            ("Between judging appointments", "judging_gap", "minutes"),
            ("Teams per judging sprint", "sprint_size", "before an extra break"),
            ("Judging sprint break", "sprint_break", "minutes"),
        ]
        for row, (label, key, help_text) in enumerate(rows, start=1):
            self._entry_row(body, row, label, key, help_text)
        ttk.Separator(body).grid(row=9, column=0, columnspan=3, sticky="ew", pady=16)
        ttk.Label(body, text="Optimizer", style="Section.TLabel").grid(
            row=10, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        self._entry_row(body, 11, "Time limit per stage", "solver_limit", "seconds")
        self._entry_row(body, 12, "Finish allowance", "finish_allowance", "minutes")
        ttk.Label(body, text="Objective mode").grid(row=13, column=0, sticky="w", pady=7)
        ttk.Combobox(
            body,
            textvariable=self._var("objective_mode"),
            values=("lexicographic", "weighted"),
            state="readonly",
            width=25,
        ).grid(row=13, column=1, sticky="w", pady=7)
        self._entry_row(body, 14, "Earliest-finish weight", "finish_weight", "weighted mode")
        self._entry_row(body, 15, "Judging-separation weight", "separation_weight", "weighted mode")
        self._entry_row(body, 16, "Minimum-gap weight", "gap_weight", "weighted mode")

    def _build_results_tab(self) -> None:
        buttons = ttk.Frame(self.results_tab)
        buttons.pack(fill="x", pady=(0, 10))
        self.open_results_button = ttk.Button(
            buttons, text="Open results folder", command=self.open_results, state="disabled"
        )
        self.open_results_button.pack(side="left")
        self.open_timeline_button = ttk.Button(
            buttons, text="Open room timeline", command=self.open_timeline, state="disabled"
        )
        self.open_timeline_button.pack(side="left", padx=(8, 0))
        self.result_text = tk.Text(
            self.results_tab,
            wrap="word",
            state="disabled",
            font=("Consolas", 10),
            padx=12,
            pady=12,
        )
        self.result_text.pack(fill="both", expand=True)

    def _set_values_from_config(
        self,
        config: Config,
        tournament_details: Mapping[str, Any] | None = None,
    ) -> None:
        tournament_details = tournament_details or {
            "table_rooms": [
                f"Table {index + 1}" for index in range(config.tournament.ntables)
            ],
            "project_rooms": [
                f"Project {index + 1}"
                for index in range(config.tournament.njudging_rooms)
            ],
            "design_rooms": [
                f"Design {index + 1}"
                for index in range(config.tournament.njudging_rooms)
            ],
        }
        judging_start = config.day.judging_start_time
        if not judging_start:
            judging_start = minute_to_time(
                parse_time(config.day.start_time) + config.day.opening_ceremony_duration
            ).strftime("%H:%M")
        mapping = {
            "project_rooms": ", ".join(tournament_details["project_rooms"]),
            "design_rooms": ", ".join(tournament_details["design_rooms"]),
            "table_names": ", ".join(tournament_details["table_rooms"]),
            "opening_start": config.day.start_time,
            "opening_duration": str(config.day.opening_ceremony_duration),
            "judging_start": judging_start,
            "matches_start": config.day.matches_start_time,
            "lunch_start": config.day.lunch_start,
            "lunch_duration": str(config.day.nminutes_lunch),
            "closing_start": config.day.closing_ceremony_time,
            "closing_latest": config.day.closing_ceremony_time_latest
            or config.day.closing_ceremony_time,
            "deliberation_duration": str(config.day.deliberation_duration),
            "minimum_gap": str(config.team.time_between_events),
            "round_1_duration": str(config.table.nminutes_table_rnd1),
            "later_round_duration": str(config.table.nminutes_table_allrounds),
            "match_break": str(config.table.match_break_duration),
            "execution_duration": str(config.table.nminutes_execution),
            "judging_duration": str(config.judging.nminutes_judging),
            "judging_gap": str(config.judging.nminutes_between_judging),
            "sprint_size": str(config.judging.nteams_per_judging_sprint),
            "sprint_break": str(config.judging.extra_sprint_break),
            "solver_limit": str(config.solver.max_time_seconds),
            "finish_allowance": str(config.solver.finish_allowance),
            "objective_mode": config.solver.objective_mode,
            "finish_weight": str(config.solver.overall_finish_weight),
            "separation_weight": str(config.solver.judging_separation_weight),
            "gap_weight": str(config.solver.minimum_gap_weight),
        }
        for key, value in mapping.items():
            self._var(key).set(value)

    def new_setup(self) -> None:
        self.base_config = Config()
        self._set_values_from_config(self.base_config)
        setup = (Path.cwd() / "tournament_input").resolve()
        self._var("input_directory").set(str(setup))
        self._var("output_directory").set(str(setup / "output"))
        self._var("tournament_date").set(datetime.now().strftime("%m/%d/%Y"))
        self._replace_teams(
            [(str(index), f"Team {index}", "0", "") for index in range(1, 21)]
        )
        latex = shutil.which("pdflatex")
        self.pdf_var.set(bool(latex))
        if latex:
            self.pdf_check.configure(state="normal")
            self.latex_note.configure(text="PDF support detected.")
        else:
            self.pdf_check.configure(state="disabled")
            self.latex_note.configure(
                text="PDF support was not detected. CSV, HTML, statistics, and saved schedules will still be created."
            )
        self.last_result = None
        self.open_results_button.configure(state="disabled")
        self.open_timeline_button.configure(state="disabled")
        self._write_results("Ready for a new tournament.\n\nImport a team CSV or edit the starter rows.")
        self.status_var.set("Ready")
        self.notebook.select(self.setup_tab)

    def _browse_directory(self, key: str) -> None:
        current = self._var(key).get().strip()
        selected = filedialog.askdirectory(
            parent=self, initialdir=current if Path(current).is_dir() else Path.cwd()
        )
        if selected:
            self._var(key).set(selected)

    def _replace_teams(self, rows: Sequence[Sequence[Any]]) -> None:
        self.team_tree.delete(*self.team_tree.get_children())
        for row in rows:
            values = ["" if pd.isna(value) else str(value) for value in row]
            self.team_tree.insert("", "end", values=values)
        self._update_team_count()

    def _update_team_count(self) -> None:
        count = len(self.team_tree.get_children())
        suffix = " (a filler opponent will be added)" if count % 2 else ""
        self.team_count_var.set(f"{count} teams{suffix}")

    def _team_rows(self) -> list[tuple[Any, ...]]:
        return [self.team_tree.item(item, "values") for item in self.team_tree.get_children()]

    def import_teams(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self,
            title="Import team list",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
        )
        if not filename:
            return
        try:
            teams = validate_teams(pd.read_csv(filename))
        except Exception as error:
            messagebox.showerror("Could not import teams", str(error), parent=self)
            return
        self._replace_teams(teams.itertuples(index=False, name=None))
        self.status_var.set(f"Imported {len(teams)} teams")

    def add_team(self) -> None:
        dialog = TeamDialog(self)
        if dialog.result:
            self.team_tree.insert("", "end", values=dialog.result)
            self._update_team_count()

    def edit_team(self) -> None:
        selected = self.team_tree.selection()
        if not selected:
            messagebox.showinfo("Edit team", "Select a team first.", parent=self)
            return
        item = selected[0]
        dialog = TeamDialog(self, self.team_tree.item(item, "values"))
        if dialog.result:
            self.team_tree.item(item, values=dialog.result)

    def remove_teams(self) -> None:
        selected = self.team_tree.selection()
        if not selected:
            return
        for item in selected:
            self.team_tree.delete(item)
        self._update_team_count()

    def _form_values(self) -> dict[str, str]:
        return {key: variable.get() for key, variable in self.values.items()}

    def _request_from_form(self) -> ScheduleRequest:
        values = self._form_values()
        config = build_config(values, self.base_config)
        teams = validate_teams(self._team_rows())
        config.tournament.nteams = len(teams)
        config.validate()
        date = validate_tournament_date(values["tournament_date"])
        input_text = values["input_directory"].strip()
        output_text = values["output_directory"].strip()
        if not input_text or not output_text:
            raise ValueError("Choose both a setup folder and a results folder.")
        return ScheduleRequest(
            config=config,
            teams=teams,
            table_rooms=_room_names(values["table_names"], "table"),
            project_rooms=_room_names(values["project_rooms"], "Innovation Project"),
            design_rooms=_room_names(values["design_rooms"], "Robot Design"),
            input_directory=Path(input_text).expanduser().resolve(),
            output_directory=Path(output_text).expanduser().resolve(),
            tournament_date=date,
            generate_pdfs=self.pdf_var.get(),
        )

    def save_setup(self) -> None:
        try:
            request = self._request_from_form()
            save_request_inputs(request)
        except Exception as error:
            messagebox.showerror("Could not save setup", str(error), parent=self)
            return
        self.status_var.set("Setup saved")
        messagebox.showinfo(
            "Setup saved", f"Reusable setup files were saved in:\n{request.input_directory}", parent=self
        )

    def load_setup(self) -> None:
        directory = filedialog.askdirectory(parent=self, title="Choose a saved setup folder")
        if not directory:
            return
        folder = Path(directory)
        try:
            config = Config.from_json(folder / "config.json")
            with (folder / "tournament_details.json").open(encoding="utf-8") as handle:
                details = json.load(handle)
            team_path = Path(details["teamlist"])
            if not team_path.is_absolute():
                team_path = folder / team_path
            teams = validate_teams(pd.read_csv(team_path))
            metadata_path = folder / "gui_settings.json"
            metadata: dict[str, Any] = {}
            if metadata_path.is_file():
                with metadata_path.open(encoding="utf-8") as handle:
                    metadata = json.load(handle)
        except Exception as error:
            messagebox.showerror(
                "Could not open setup",
                f"Choose a folder containing config.json, tournament_details.json, and the team CSV.\n\n{error}",
                parent=self,
            )
            return
        self.base_config = config
        self._set_values_from_config(config, details)
        self._var("input_directory").set(str(folder.resolve()))
        self._var("output_directory").set(
            str(Path(metadata.get("output_directory", folder / "output")).resolve())
        )
        self._var("tournament_date").set(
            metadata.get("tournament_date", datetime.now().strftime("%m/%d/%Y"))
        )
        if shutil.which("pdflatex"):
            self.pdf_var.set(bool(metadata.get("generate_pdfs", True)))
        self._replace_teams(teams.itertuples(index=False, name=None))
        self.status_var.set(f"Loaded setup from {folder}")
        self.notebook.select(self.setup_tab)

    def generate(self) -> None:
        try:
            request = self._request_from_form()
        except Exception as error:
            messagebox.showerror("Check the setup", str(error), parent=self)
            return
        self.generate_button.configure(state="disabled")
        self.progress.start(12)
        self.status_var.set("Optimizing schedule… this may take several minutes")
        self._write_results(
            "Generating schedule…\n\nThe optimizer can run multiple stages. You may continue to view the setup while it works."
        )
        self.notebook.select(self.results_tab)
        thread = threading.Thread(target=self._run_worker, args=(request,), daemon=True)
        thread.start()

    def _run_worker(self, request: ScheduleRequest) -> None:
        try:
            result = run_request(request)
        except Exception as error:
            self.worker_messages.put(("error", (error, traceback.format_exc())))
        else:
            self.worker_messages.put(("success", (request, result)))

    def _poll_worker(self) -> None:
        try:
            kind, payload = self.worker_messages.get_nowait()
        except queue.Empty:
            pass
        else:
            self.progress.stop()
            self.generate_button.configure(state="normal")
            if kind == "success":
                request, result = payload
                self._show_success(request, result)
            else:
                error, details = payload
                self._show_error(error, details)
        self.after(150, self._poll_worker)

    def _show_success(self, request: ScheduleRequest, result: WorkflowResult) -> None:
        self.last_result = result
        stages = "\n".join(
            f"  • {name.replace('_', ' ').title()}: {stage.status} ({stage.wall_time_seconds:.1f}s)"
            for name, stage in result.optimization.stages.items()
        )
        files = "\n".join(f"  • {Path(path).name}" for path in result.files)
        text = (
            "SCHEDULE COMPLETE\n\n"
            f"Minimum team gap: {result.validation.minimum_gap} minutes\n"
            f"Limiting team: {result.validation.limiting_team}\n"
            f"Results folder: {request.output_directory}\n\n"
            f"Optimizer stages\n{stages}\n\nCreated files\n{files}"
        )
        self._write_results(text)
        self.status_var.set("Schedule complete")
        self.open_results_button.configure(state="normal")
        timeline = request.output_directory / "all_rooms_schedule.html"
        self.open_timeline_button.configure(state="normal" if timeline.is_file() else "disabled")
        messagebox.showinfo(
            "Schedule complete",
            f"The schedule is ready.\n\nMinimum team gap: {result.validation.minimum_gap} minutes",
            parent=self,
        )

    def _show_error(self, error: Exception, details: str) -> None:
        friendly = str(error) or error.__class__.__name__
        self._write_results(
            "SCHEDULE COULD NOT BE GENERATED\n\n"
            + friendly
            + "\n\nTechnical details\n"
            + details
        )
        self.status_var.set("Schedule generation failed")
        messagebox.showerror(
            "Schedule could not be generated",
            friendly + "\n\nReview the inputs or increase the solver time limit, then try again.",
            parent=self,
        )

    def _write_results(self, value: str) -> None:
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", value)
        self.result_text.configure(state="disabled")

    def open_results(self) -> None:
        path = Path(self._var("output_directory").get())
        if path.is_dir():
            open_path(path)

    def open_timeline(self) -> None:
        timeline = Path(self._var("output_directory").get()) / "all_rooms_schedule.html"
        if timeline.is_file():
            webbrowser.open(timeline.resolve().as_uri())


def main() -> None:
    app = SchedulerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
