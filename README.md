# FLL schedule optimizer

This branch replaces randomized schedule generation with an OR-Tools CP-SAT model.
By default it finds the earliest competitive finish, maximizes the time from
judging completion to table completion, and then maximizes the smallest gap
between any team's events. It retains the `main` branch's `Tournament.events`
DataFrame and FLLTournament CSV contracts. An optional weighted objective mode
allows those three goals to be traded against one another.

Table counts may be any even number. Tables are fixed into adjacent pairs in
configuration order (`1+2`, `3+4`, and so on). Match execution uses the head
referee for five minutes and therefore never overlaps another match execution;
the remaining scoring time continues to occupy that table pair but may overlap
the next match on a different pair. The defaults are five scoring minutes in
Round 1 and three scoring minutes in Rounds 2 and 3.

NOTE: TO GET THE SHORTEST TOURNAMENT POSSIBLE, PUT THE END TIME AS EARLY AS POSSIBLE

## Desktop app

`scheduler_gui.py` is a small native launcher for already-created tournament
inputs. Choose either `config.json` or an existing solved template, then select
`teamlist.csv` and `tournament_details.json` explicitly. The GUI never creates or
edits configuration, room, or team files. When using `config.json`, clear the
operational-output checkbox to run only the optimizer and create an anonymous
`tournament_schedule_template_*.csv`; team, tournament-details, and date fields
are not required for that mode.

For development on Windows, launch the source directly from the build environment:

```powershell
.\build_venv\Scripts\python.exe .\scheduler_gui.py
```

This shows source changes immediately; rebuilding the executable is only needed
when you want a new distributable `.exe`.

To hand the application to a Windows user who does not have Python, build the
standalone executable once from PowerShell on a Windows machine with Python 3.12
or 3.13:

```powershell
.\build_windows.ps1
```

Distribute `dist\FLL Schedule Generator.exe`. The recipient can double-click that
file; Python and the repository are not required. CSV, HTML, statistics, and saved
schedule files work without additional software. The five PDFs additionally need
`pdflatex` on the recipient's `PATH` (for example, from MiKTeX); the app detects
this and disables the PDF option when it is unavailable.

## Setup

The project uses the `venv` directory (not `.venv`). From Bash in Linux or WSL,
set it up with:

```sh
./setup_venv.sh
```

PDF generation also requires `pdflatex`. On Ubuntu/WSL it can be installed from
the TeX Live packages if it is not already available.

## Easiest setup

From Bash, run:

```sh
./run_setup.sh
```

The wizard asks for tournament times, rooms, teams, and solver settings. It writes
`config.json`, `tournament_details.json`, and `teamlist.csv`, then offers to run the
optimizer and create all six legacy schedule files.

The direct equivalent is:

```sh
venv/bin/python setup_tournament.py
```

## Direct command

```sh
venv/bin/python schedule_generator.py \
  --config config.json \
  --tournament_details tournament_details.json \
  --output_folder output \
  --tournament_date 1/31/2026
```

Use `--skip_pdf` when LaTeX is unavailable. Without that flag, the command creates
the FLLT CSV plus emcee, judging, referee, team, and room PDFs. Every run also
creates `all_rooms_schedule.html`, an interactive timeline containing all table,
Innovation, and Design rooms at once. It also writes `stats.txt` with team-gap,
room-day-length, utilization, and solver statistics.

Tournament-specific names are kept outside the solver config:

```json
{
  "teamlist": "teamlist.csv",
  "table_rooms": ["Table 1", "Table 2"],
  "project_rooms": ["P1", "P2"],
  "design_rooms": ["D1", "D2"]
}
```

The team list requires `Team #`, `Team Name`, and `Distance`; `Note` is optional.
See `PRINT_OUTPUT_SPECS.md` for the printout compatibility contract.
See `RUNBOOK.md` for the complete standalone workflow and the ready-to-run 20-team
example.

If a template is already solved, no configuration file is needed:

```sh
venv/bin/python render_template.py \
  --template template.csv \
  --tournament-details tournament_details.json \
  --output output/rendered
```

Add `--tournament-date 1/31/2027` when an FLLTournament CSV is also needed. This
path does not run the optimizer; it fills the anonymous solution with the room
names and team list referenced by `tournament_details.json`.

## End-to-end verification

Run the complete four-team optimizer and PDF smoke test from Bash:

```sh
./run_e2e_test.sh
```

The direct equivalent is:

```sh
venv/bin/python e2e_test.py
```

The test creates `e2e_output`, validates the schedule, renders every PDF, and fails
if a required output is missing or empty. Use `--skip-pdf` to test only the solver,
validation, and CSV path.
