from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import traceback
from typing import Any
import webbrowser

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from config import Config
from schedule import Tournament
from workflow import (
    AnonymousTemplateResult,
    TemplateRenderResult,
    WorkflowResult,
    generate_anonymous_template,
    generate_schedule,
    render_solved_template,
)


APP_NAME = "FLL Schedule Generator"


@dataclass(frozen=True)
class ScheduleRequest:
    mode: str
    config_path: Path | None
    template_csv: Path | None
    team_list_path: Path | None
    details_path: Path | None
    output_directory: Path
    tournament_date: str | None
    create_operational_outputs: bool


def validate_tournament_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value.strip(), "%m/%d/%Y")
    except ValueError as error:
        raise ValueError("Tournament date must use M/D/YYYY format.") from error
    return f"{parsed.month}/{parsed.day}/{parsed.year}"


def existing_file(value: str, label: str) -> Path:
    if not value.strip():
        raise ValueError(f"Choose {label}.")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    return path


def load_tournament_details(
    details_path: str | Path,
    team_list_path: str | Path,
) -> dict[str, Any]:
    """Load room details and override its team list with the explicit GUI path."""
    details_file = Path(details_path).expanduser().resolve()
    try:
        with details_file.open(encoding="utf-8") as handle:
            details = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read tournament_details.json: {error}") from error
    if not isinstance(details, dict):
        raise ValueError("tournament_details.json must contain a JSON object.")
    details["teamlist"] = str(Path(team_list_path).expanduser().resolve())
    return details


def run_request(
    request: ScheduleRequest,
) -> WorkflowResult | TemplateRenderResult | AnonymousTemplateResult:
    if request.mode == "template":
        if (
            request.template_csv is None
            or request.details_path is None
            or request.team_list_path is None
        ):
            raise ValueError("Template rendering requires Tournament Details.")
        return render_solved_template(
            request.template_csv,
            request.details_path,
            request.output_directory,
            tournament_date=request.tournament_date,
            generate_pdfs=True,
            team_list_csv=request.team_list_path,
        )

    if request.mode != "config" or request.config_path is None:
        raise ValueError("Choose either config.json or a schedule template.")
    config = Config.from_json(request.config_path)
    if not request.create_operational_outputs:
        return generate_anonymous_template(config, request.output_directory)
    if (
        request.details_path is None
        or request.team_list_path is None
        or request.tournament_date is None
    ):
        raise ValueError("Operational outputs require Tournament Details.")
    details = load_tournament_details(request.details_path, request.team_list_path)
    Tournament.room_names_from_details(config, details)
    return generate_schedule(
        config,
        details,
        request.output_directory,
        request.tournament_date,
        generate_pdfs=True,
        details_base_directory=request.details_path.parent,
    )


def open_path(path: Path) -> None:
    path = path.resolve()
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class SchedulerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("900x720")
        self.minsize(760, 650)
        self.worker_messages: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._build_style()
        self._build_ui()
        self._set_initial_values()
        self.after(150, self._poll_worker)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Help.TLabel", font=("Segoe UI", 9), foreground="#4b5563")
        style.configure("Or.TLabel", font=("Segoe UI", 10, "bold"), foreground="#6b7280")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 9))

    def _file_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        browse_command: Any,
        radio_value: str | None = None,
    ) -> tuple[ttk.Entry, ttk.Button]:
        if radio_value:
            label_widget: Any = ttk.Radiobutton(
                parent,
                text=label,
                variable=self.mode_var,
                value=radio_value,
                command=self._update_mode,
            )
        else:
            label_widget = ttk.Label(parent, text=label)
        label_widget.grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        button = ttk.Button(parent, text="Browse…", command=browse_command)
        button.grid(row=row, column=2, sticky="w", padx=(12, 0), pady=6)
        return entry, button

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=(24, 18))
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(16, weight=1)

        ttk.Label(root, text=APP_NAME, style="Title.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(
            root,
            text="Run an existing configuration or fill an existing solved template.",
            style="Help.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 18))

        ttk.Label(root, text="Tournament Configuration", style="Section.TLabel").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )
        self.mode_var = tk.StringVar()
        self.config_var = tk.StringVar()
        self.template_var = tk.StringVar()
        self.config_entry, self.config_button = self._file_row(
            root,
            3,
            "config.json",
            self.config_var,
            lambda: self._choose_file(self.config_var, "Choose config.json", "*.json"),
            "config",
        )
        ttk.Label(root, text="OR", style="Or.TLabel").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=2
        )
        self.template_entry, self.template_button = self._file_row(
            root,
            5,
            "tournament_schedule_template.csv",
            self.template_var,
            lambda: self._choose_file(
                self.template_var, "Choose solved schedule template", "*.csv"
            ),
            "template",
        )

        ttk.Separator(root).grid(row=6, column=0, columnspan=3, sticky="ew", pady=14)
        self.team_var = tk.StringVar()
        self.details_var = tk.StringVar()
        ttk.Label(root, text="Tournament Details", style="Section.TLabel").grid(
            row=7, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )
        self.team_entry, self.team_button = self._file_row(
            root,
            8,
            "teamlist.csv",
            self.team_var,
            lambda: self._choose_file(self.team_var, "Choose teamlist.csv", "*.csv"),
        )
        self.details_entry, self.details_button = self._file_row(
            root,
            9,
            "tournament_details.json",
            self.details_var,
            lambda: self._choose_file(
                self.details_var, "Choose tournament_details.json", "*.json"
            ),
        )

        ttk.Label(root, text="Tournament date").grid(
            row=10, column=0, sticky="w", padx=(0, 12), pady=6
        )
        self.date_var = tk.StringVar()
        self.date_entry = ttk.Entry(root, textvariable=self.date_var, width=24)
        self.date_entry.grid(
            row=10, column=1, sticky="w", pady=6
        )
        ttk.Label(root, text="M/D/YYYY", style="Help.TLabel").grid(
            row=10, column=2, sticky="w", padx=(12, 0), pady=6
        )
        ttk.Label(
            root,
            text="Required only when creating filled tournament outputs.",
            style="Help.TLabel",
        ).grid(row=11, column=0, columnspan=3, sticky="w", pady=(0, 4))

        ttk.Separator(root).grid(row=12, column=0, columnspan=3, sticky="ew", pady=14)
        ttk.Label(root, text="Output", style="Section.TLabel").grid(
            row=13, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )
        self.output_var = tk.StringVar()
        self._file_row(
            root,
            14,
            "Results folder",
            self.output_var,
            self._choose_output_folder,
        )
        self.outputs_var = tk.BooleanVar()
        self.outputs_check = ttk.Checkbutton(
            root,
            text="Create fllTournament.csv, schedule printouts, and .html visualizer",
            variable=self.outputs_var,
            command=self._update_output_fields,
        )
        self.outputs_check.grid(
            row=15, column=0, columnspan=3, sticky="w", pady=(8, 12)
        )

        results = ttk.LabelFrame(root, text="Status", padding=10)
        results.grid(row=16, column=0, columnspan=3, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.result_text = tk.Text(
            results,
            wrap="word",
            state="disabled",
            height=9,
            font=("Consolas", 9),
            padx=8,
            pady=8,
        )
        self.result_text.grid(row=0, column=0, columnspan=3, sticky="nsew")
        self.open_results_button = ttk.Button(
            results,
            text="Open results folder",
            command=self.open_results,
            state="disabled",
        )
        self.open_results_button.grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.open_timeline_button = ttk.Button(
            results,
            text="Open room timeline",
            command=self.open_timeline,
            state="disabled",
        )
        self.open_timeline_button.grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0)
        )

        footer = ttk.Frame(root)
        footer.grid(row=17, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        self.status_var = tk.StringVar(value="Choose the required files")
        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=160)
        self.progress.pack(side="left", padx=10)
        self.run_button = ttk.Button(
            footer,
            text="Generate schedule",
            style="Primary.TButton",
            command=self.generate,
        )
        self.run_button.pack(side="right")

    def _set_initial_values(self) -> None:
        self.mode_var.set("config")
        self.date_var.set(datetime.now().strftime("%m/%d/%Y"))
        self.output_var.set(str((Path.cwd() / "output").resolve()))
        self.outputs_var.set(True)
        self._update_mode()
        self._write_results(
            "Choose config.json to run the optimizer. Uncheck the output package to "
            "create only the anonymous schedule template; Tournament Details are then optional."
        )

    def _update_mode(self) -> None:
        config_mode = self.mode_var.get() == "config"
        self.config_entry.configure(state="normal" if config_mode else "disabled")
        self.config_button.configure(state="normal" if config_mode else "disabled")
        self.template_entry.configure(state="disabled" if config_mode else "normal")
        self.template_button.configure(state="disabled" if config_mode else "normal")
        if not config_mode:
            self.outputs_var.set(True)
        self.outputs_check.configure(state="normal" if config_mode else "disabled")
        self.run_button.configure(
            text="Generate schedule" if config_mode else "Render template"
        )
        self._update_output_fields()

    def _update_output_fields(self) -> None:
        enabled = self.outputs_var.get() or self.mode_var.get() == "template"
        state = "normal" if enabled else "disabled"
        for widget in (
            self.team_entry,
            self.team_button,
            self.details_entry,
            self.details_button,
            self.date_entry,
        ):
            widget.configure(state=state)

    def _choose_file(self, variable: tk.StringVar, title: str, pattern: str) -> None:
        current = variable.get().strip()
        selected = filedialog.askopenfilename(
            parent=self,
            title=title,
            initialdir=Path(current).parent if current else Path.cwd(),
            filetypes=(("Expected file", pattern), ("All files", "*.*")),
        )
        if selected:
            variable.set(selected)

    def _choose_output_folder(self) -> None:
        current = Path(self.output_var.get())
        selected = filedialog.askdirectory(
            parent=self,
            title="Choose results folder",
            initialdir=current if current.is_dir() else current.parent,
        )
        if selected:
            self.output_var.set(selected)

    def _request_from_form(self) -> ScheduleRequest:
        mode = self.mode_var.get()
        config_path = None
        template_csv = None
        if mode == "config":
            config_path = existing_file(self.config_var.get(), "config.json")
        elif mode == "template":
            template_csv = existing_file(
                self.template_var.get(), "tournament_schedule_template.csv"
            )
        else:
            raise ValueError("Choose config.json or a schedule template.")
        create_outputs = self.outputs_var.get() or mode == "template"
        team_list_path = None
        details_path = None
        tournament_date = None
        if create_outputs:
            team_list_path = existing_file(self.team_var.get(), "teamlist.csv")
            details_path = existing_file(
                self.details_var.get(), "tournament_details.json"
            )
            tournament_date = validate_tournament_date(self.date_var.get())
        output_text = self.output_var.get().strip()
        if not output_text:
            raise ValueError("Choose a results folder.")
        return ScheduleRequest(
            mode=mode,
            config_path=config_path,
            template_csv=template_csv,
            team_list_path=team_list_path,
            details_path=details_path,
            output_directory=Path(output_text).expanduser().resolve(),
            tournament_date=tournament_date,
            create_operational_outputs=create_outputs,
        )

    def generate(self) -> None:
        try:
            request = self._request_from_form()
        except Exception as error:
            messagebox.showerror("Check the files", str(error), parent=self)
            return
        self.run_button.configure(state="disabled")
        self.progress.start(12)
        if request.mode == "template":
            self.status_var.set("Rendering solved template…")
            action = f"Template: {request.template_csv}"
        else:
            if request.create_operational_outputs:
                self.status_var.set("Optimizing schedule… this may take several minutes")
                action = f"Config: {request.config_path}"
            else:
                self.status_var.set("Optimizing anonymous schedule template…")
                action = f"Optimizer-only config: {request.config_path}"
        tournament_details = ""
        if request.team_list_path is not None and request.details_path is not None:
            tournament_details = (
                f"\nTeam list: {request.team_list_path}"
                f"\nTournament details: {request.details_path}"
            )
        self._write_results(
            f"{action}"
            f"{tournament_details}\n"
            f"Results: {request.output_directory}"
        )
        threading.Thread(
            target=self._run_worker,
            args=(request,),
            daemon=True,
        ).start()

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
            self.run_button.configure(state="normal")
            if kind == "success":
                request, result = payload
                self._show_success(request, result)
            else:
                error, details = payload
                self._show_error(error, details)
        self.after(150, self._poll_worker)

    def _show_success(
        self,
        request: ScheduleRequest,
        result: WorkflowResult | TemplateRenderResult | AnonymousTemplateResult,
    ) -> None:
        if isinstance(result, AnonymousTemplateResult):
            stages = "\n".join(
                f"  • {name.replace('_', ' ').title()}: "
                f"{stage.status} ({stage.wall_time_seconds:.1f}s)"
                for name, stage in result.optimization.stages.items()
            )
            summary = f"Optimizer stages\n{stages}\n\n"
            heading = "ANONYMOUS TEMPLATE COMPLETE"
            gap_line = f"Minimum optimized gap: {result.optimization.minimum_gap} minutes\n"
        elif isinstance(result, WorkflowResult):
            stages = "\n".join(
                f"  • {name.replace('_', ' ').title()}: "
                f"{stage.status} ({stage.wall_time_seconds:.1f}s)"
                for name, stage in result.optimization.stages.items()
            )
            summary = f"Optimizer stages\n{stages}\n\n"
            heading = "SCHEDULE COMPLETE"
            gap_line = f"Minimum team gap: {result.validation.minimum_gap} minutes\n"
        else:
            summary = "Existing template rendered; optimizer was not run.\n\n"
            heading = "TEMPLATE RENDER COMPLETE"
            gap_line = f"Minimum team gap: {result.validation.minimum_gap} minutes\n"
        files = "\n".join(f"  • {Path(path).name}" for path in result.files)
        self._write_results(
            f"{heading}\n\n"
            f"{gap_line}"
            f"Results folder: {request.output_directory}\n\n"
            f"{summary}Created files\n{files}"
        )
        self.status_var.set("Complete")
        self.open_results_button.configure(state="normal")
        timeline = request.output_directory / "all_rooms_schedule.html"
        self.open_timeline_button.configure(
            state="normal" if timeline.is_file() else "disabled"
        )

    def _show_error(self, error: Exception, details: str) -> None:
        friendly = str(error) or error.__class__.__name__
        self._write_results(
            "RUN FAILED\n\n" + friendly + "\n\nTechnical details\n" + details
        )
        self.status_var.set("Failed")
        messagebox.showerror("Run failed", friendly, parent=self)

    def _write_results(self, value: str) -> None:
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", value)
        self.result_text.configure(state="disabled")

    def open_results(self) -> None:
        output = Path(self.output_var.get())
        if output.is_dir():
            open_path(output)

    def open_timeline(self) -> None:
        timeline = Path(self.output_var.get()) / "all_rooms_schedule.html"
        if timeline.is_file():
            webbrowser.open(timeline.resolve().as_uri())


def main() -> None:
    SchedulerApp().mainloop()


if __name__ == "__main__":
    main()
