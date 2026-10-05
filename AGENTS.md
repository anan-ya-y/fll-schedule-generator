# Repository guidance

## Purpose and layout

This project generates FIRST LEGO League tournament schedules from configuration
and team data, or fills a precalculated schedule template with tournament details.
It exports an FLLTournament (FLLT) CSV and schedules rendered through PyLaTeX.

- `schedule_generator.py`: argparse CLI and export orchestration.
- `config.py`: defaults, derived configuration, JSON serialization, and random seed.
- `schedule.py`: `Tournament`, template generation, team assignment, and validation.
- `schedule_latex.py`: FLLT CSV export and PDF rendering functions.
- `utils.py`: time arithmetic, overlap detection, and the `Event` helper.
- `make_lunch_longer.py`: adjusts lunch duration and shifts later template events.
- `get_earliest_closing_ceremony_time.py`: estimates closing time from a template.
- `precalculated_templates/`: saved tournament inputs; preserve these as historical
  data unless the task explicitly requires editing them.
- `test.py`: standalone PyLaTeX demo that writes a PDF, not an automated test suite.

## Development and execution

Run commands from the repository root. Use a virtual environment and the pinned
dependencies in `requirements.txt`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

PDF generation also requires an installed LaTeX compiler and the packages used by
PyLaTeX (including geometry, xcolor, and table-related packages). Python dependencies
alone are insufficient.

Example CLI invocation with user-supplied inputs:

```sh
.venv/bin/python schedule_generator.py \
  --config /path/to/config.json \
  --tournament_details /path/to/tournament_details.json \
  --template_csv /path/to/template.csv \
  --output_folder /tmp/fll-schedule-output \
  --tournament_date 1/31/2026
```

`--config` and `--template_csv` are optional; omitting the template triggers
randomized schedule generation, which can take many attempts. Prefer an existing
template for smoke checks. `--tournament_details` and `--tournament_date` are required.
The date string is passed through to FLLT; preserve the requested format.

The CLI writes `config_generated.json` in the current working directory even when
loading a supplied configuration. It currently calls only `create_fllt` and
`create_emcee_schedule`; the other four PDF calls are commented out. Do not infer
successful generation of six files from its final printed message.

The checked-in tournament-details example references `teamlist_2026_sectional.csv`,
which is not tracked. Supply a valid team list for end-to-end runs. Its path is
resolved against the working directory, not the tournament-details file's directory.

## Data contracts and scheduling rules

- Template columns are `Time`, `EventName`, `RoundNo`, `Room`, `Duration`, and `Team`.
  CSV times use `HH:MM:SS`; in-memory times are `datetime.time` objects and durations
  are minutes. Config defaults accept `HH:MM`; serialized config times use `HH:MM:SS`.
- Event names such as `Project`, `Design`, `Table`, and `Lunch` drive filtering and
  exports. Preserve their spelling and the CSV schemas unless changing the contract
  intentionally.
- Template team IDs run from 1 through the configured team count. `Team = -1` means
  unassigned and `Team = -2` means a break/no team. Actual team numbers replace IDs
  after template validation; `Team ID` retains the original identity.
- Team lists require `Team #`, `Team Name`, and `Distance`; `Note` is optional.
  Tournament details require `teamlist`, `design_rooms`, and `project_rooms`.
- Odd configured team counts are rounded up. Team lists may have the template's
  team count or one fewer; the latter adds `DUMMY_TEAM_NO` (99999). Keep dummy-team
  handling consistent, including its exclusion from FLLT exports.
- Preserve no-overlap checks, the configured minimum gap between team events,
  opponent diversity, and table diversity. Also check event counts when changing
  assignment logic; `verify_schedule` does not explicitly check them all.
- `verify_schedule` can modify table assignments while repairing table diversity.
  It is not a read-only check. Its helpers use template team IDs; account for the
  later conversion to actual team numbers when validating filled schedules.
- Preserve seeded NumPy randomness for reproducible investigations. Config loading
  does not itself reseed NumPy, so inspect initialization before relying on a JSON
  seed. The `team` configuration section is intentionally excluded from JSON export.
- FLLT export maps `Design` to `Robot` and emits a specific ordered column schema;
  keep downstream import compatibility.

## Changes and validation

Follow the surrounding Python style: four-space indentation, snake_case functions,
and the existing small-module layout. Keep changes focused; avoid unrelated
formatting, dependency upgrades, or large framework additions.

There is no configured automated test runner, formatter, or CI workflow. For Python
changes, start with a syntax check of the affected files:

```sh
python3 -m py_compile config.py schedule.py schedule_generator.py schedule_latex.py utils.py
```

For scheduling changes, use a small reproducible configuration or a copied existing
template and inspect the relevant validation results, team event counts, gaps,
opponents, and table assignments. Add focused regression tests for corrected logic
when appropriate. For export changes, inspect CSV column order and values or render
the affected PDFs when LaTeX is available. Do not run `test.py` as a test suite or
import CLI scripts for a side-effect-free check: they execute code at module scope.

Keep smoke-test outputs in a temporary directory. Do not commit generated schedules,
PDFs, LaTeX auxiliary files, local team data, virtual environments, or
`config_generated.json` unless explicitly requested. Report checks actually run and
any missing inputs or tools that prevented end-to-end verification.
