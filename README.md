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

Tournament details use the legacy shape:

```json
{
  "teamlist": "teamlist.csv",
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
./run_template.sh template.csv teamlist.csv output/rendered
```

Add a tournament date as the fourth argument when an FLLTournament CSV is also
needed.

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
