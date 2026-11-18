# Running the FLL scheduler without assistance

All commands below are run from Bash in Linux or WSL, from the repository root.

## Desktop interface for tournament staff

Windows users can run `FLL Schedule Generator.exe` without installing Python.
The single-screen app accepts either `config.json` or an anonymous solved-template
CSV, followed by explicit `teamlist.csv` and `tournament_details.json` paths. It
does not edit or create tournament inputs. With `config.json`, uncheck the filled
output package to run only the optimizer and produce a reusable anonymous template.

To prepare the distributable executable, a developer runs the following once in
PowerShell on Windows with Python 3.12 or 3.13 installed:

```powershell
.\build_windows.ps1
```

The output is `dist\FLL Schedule Generator.exe`. A LaTeX distribution such as
MiKTeX is optional: without `pdflatex`, the GUI produces all non-PDF results and
clearly disables the PDF checkbox.

## 1. Prepare the environment once

```bash
./setup_venv.sh
```

This project deliberately uses `venv`, not `.venv`. PDF generation also requires
`pdflatex`; on Ubuntu/WSL it is provided by TeX Live.

## 2. Try a checked-in example

Fast four-team example:

```bash
venv/bin/python schedule_generator.py \
  --config examples/4-team/config.json \
  --tournament_details examples/4-team/tournament_details.json \
  --output_folder output/4-team \
  --tournament_date 1/31/2027
```

Larger 20-team example:

```bash
venv/bin/python schedule_generator.py \
  --config examples/20-team/config.json \
  --tournament_details examples/20-team/tournament_details.json \
  --output_folder output/20-team \
  --tournament_date 1/31/2027
```

The 20-team solve has three stages and may use the configured 120 seconds for each
stage. When either example finishes, open `all_rooms_schedule.html` in its output
folder for the combined room view. Read `stats.txt` for team-gap and room-day-length
statistics. The folder also contains the FLLT CSV, five operational PDFs, the
normalized schedule, the anonymous template, and machine-readable metrics.

## 3. Enter your own tournament

```bash
./run_setup.sh
```

The wizard asks for teams, rooms, times, lunch, closing constraints, and solver
settings. It creates the input files and can immediately run the schedule.

Enter an even physical-table count. The order of `table_rooms` in
`tournament_details.json` names the solver's fixed pairs: the first two names are
a match pair, the next two are another pair, and so on. A pair remains occupied
for execution plus scoring (10 minutes in Round 1
and 8 minutes later by default), while the head referee is reserved only for the
first 5 execution minutes. This lets scoring overlap a later match on a different
pair without allowing match executions to overlap.

In the `day` section, `start_time` is the fixed opening-ceremony start.
`opening_ceremony_duration` blocks all judging and matches until the ceremony ends.
`judging_start_time` is the fixed first judging time and must not precede the end
of opening. `matches_start_time` controls the first table match and must not
precede the end of opening.

If you already have a team CSV, it must contain:

```text
Team #,Team Name,Distance,Note
```

`Note` is optional. `Distance` is numeric and is used to give farther-traveling
teams later earliest judging times.

## 4. Re-run saved inputs

```bash
venv/bin/python schedule_generator.py \
  --config path/to/config.json \
  --tournament_details path/to/tournament_details.json \
  --output_folder path/to/output \
  --tournament_date M/D/YYYY
```

Useful options:

- `--skip_pdf`: run the optimizer, validation, CSV, and HTML output without LaTeX.
- `--solver_time_limit 60`: override the per-stage solver limit.
- `--finish_allowance 15`: allow a later finish while maximizing the minimum gap.
- `--objective_mode weighted`: combine the objectives using configurable weights.

The default `lexicographic` mode uses strict priorities rather than weights:

1. earliest overall competitive finish;
2. largest separation between the end of judging and the end of table rounds; and
3. largest minimum team gap.

Each completed stage is locked before the next stage is solved. With the default
finish allowance of zero, later objectives may not lengthen the day. Existing idle
time counts toward table and judging break requirements, so a separate break row is
emitted only when the configured break itself is the binding gap.

To experiment with tradeoffs, set these values in the `solver` section:

```json
{
  "objective_mode": "weighted",
  "overall_finish_weight": 10,
  "judging_separation_weight": 5,
  "minimum_gap_weight": 1
}
```

Weighted mode minimizes:

```text
overall_finish_weight * overall_finish
- judging_separation_weight * (table_finish - judging_finish)
- minimum_gap_weight * minimum_team_gap
```

All terms are measured in minutes. Raising a weight makes that goal more important.
For example, increasing `judging_separation_weight` rewards earlier judging relative
to table completion; increasing `overall_finish_weight` discourages extending the
day. A separation weight larger than the finish weight can intentionally make table
rounds run later, so review the resulting finish times in `stats.txt`.

## 5. Render an already-solved template without a config

When the anonymous template has already been optimized, provide the template,
the tournament-details file (which references the team list), and an output
folder:

```bash
venv/bin/python render_template.py \
  --template path/to/tournament_schedule_template.csv \
  --tournament-details path/to/tournament_details.json \
  --output output/rendered
```

The template must contain `Time`, `EventName`, `RoundNo`, `Room`, `Duration`, and
`Team`. Positive `Team` values are anonymous IDs starting at 1; `-2` is used for
breaks and lunch.

The team list needs `Team #` and `Team Name`. `Distance` is optional in render-only
mode; when omitted, input row order determines which teams receive the earlier
anonymous schedules. `Note` is also optional.

This command does not invoke OR-Tools. It replaces generic room identifiers with
the names in `tournament_details.json`, attaches the teams, validates the solved
template, and generates all five PDFs, `all_rooms_schedule.html`, `stats.txt`, and
the normalized schedule CSV.

To also create the FLLTournament CSV, add a tournament date:

```bash
venv/bin/python render_template.py \
  --template template.csv \
  --tournament-details tournament_details.json \
  --output output/rendered \
  --tournament-date 1/31/2027
```

## 6. Test the installation

```bash
./run_e2e_test.sh
```

This solves a four-team tournament, validates it, generates every output, and fails
if a required file is missing or empty. For a faster non-PDF check:

```bash
./run_e2e_test.sh --skip-pdf
```

The automated Python tests are:

```bash
venv/bin/python -m unittest discover -s tests -v
```

## Troubleshooting

- `venv is missing`: run `./setup_venv.sh`.
- `pdflatex not found`: install TeX Live or add `--skip_pdf`.
- `INFEASIBLE`: increase the closing-time window, reduce the required team gap, or
  add judging capacity.
- `UNKNOWN`: raise the solver time limit; no feasible schedule was found in time.
- `FEASIBLE` instead of `OPTIMAL`: the output is valid, but optimality was not
  proven before the time limit.
