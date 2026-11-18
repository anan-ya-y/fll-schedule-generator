# Optimizer input fields

`config.json` describes the anonymous schedule the solver must produce.
`tournament_details.json` and `teamlist.csv` contain display names and real-team
data that are applied afterward. Times are written as 24-hour `HH:MM` (or
`HH:MM:SS`, although seconds are discarded), and durations are in minutes.
Fields may be omitted to use the defaults in `config.py`.

## `config.json`

### `tournament`

| Field | What it does |
|---|---|
| `nteams` | Number of real teams the model schedules. Every effective team gets one Project appointment, one Design appointment, and one match in each of the three table rounds. |
| `njudging_rooms` | Solver capacity for **each** judging type. The Project and Design name lists in `tournament_details.json` must each have this many entries. At most half the effective team count is activated for the first wave; any rooms beyond that cap remain unused. |
| `ntables` | Number of physical tables. It must be even and at least 2. Solver table indices are fixed into adjacent pairs: tables 1+2, 3+4, and so on. The ordered `table_rooms` list supplies their display names later. More pairs allow scoring from one match to overlap execution on another pair. |
| `ntable_rounds` | Number of robot-game rounds. The current optimizer requires this to be exactly `3`. |

If `nteams` is odd, the optimizer automatically adds one anonymous identity and
post-processing supplies filler team `99999` when the team CSV contains only the
real teams. The optimizer also prevents any pair of teams from meeting more than
once.

### `table`

| Field | What it does |
|---|---|
| `match_break_duration` | Minimum time from the end of the last match in one round to the start of the first match in the next round. It applies between R1/R2 and R2/R3. |
| `nminutes_execution` | The execution/head-referee portion at the start of every match. Consecutive match starts within a round must be at least this many minutes apart, even when multiple table pairs exist. It must be positive and cannot exceed either total match duration. |
| `nminutes_table_rnd1` | Total time a table remains occupied for a Round 1 match, including execution and scoring. |
| `nminutes_table_allrounds` | Total table-occupancy time for each Round 2 and Round 3 match, including execution and scoring. |

A complete table pair is occupied for the applicable total duration. After
`nminutes_execution`, however, the head referee can begin the next match on a
different free pair while scoring continues on the first pair.

### `judging`

| Field | What it does |
|---|---|
| `nminutes_judging` | Duration of every Project and Design appointment. |
| `nminutes_between_judging` | Minimum idle time after one appointment in a room and before the next appointment starts. |
| `nteams_per_judging_sprint` | Number of appointments in a room before an extra sprint break is required. It must be positive. |
| `extra_sprint_break` | Extra minutes added to the normal between-appointment gap after each judging sprint. |

Project and Design begin their first appointments together. Every team is
assigned exactly once to each judging type.

### `day`

| Field | What it does |
|---|---|
| `start_time` | Fixed opening-ceremony start. This is not currently an optimizable window. |
| `opening_ceremony_duration` | Blocks both judging and matches until the opening ceremony has ended. |
| `judging_start_time` | Fixed start of the first appointments in all active Project and Design rooms. If `null`, it is exactly the end of the opening ceremony. It is not currently an optimizable window. |
| `matches_start_time` | Earliest allowed start for the first Round 1 match. |
| `matches_start_time_latest` | Latest allowed start for the first Round 1 match. If `null`, the first match is fixed at `matches_start_time`. |
| `lunch_start` | Earliest allowed lunch start. Every table and judging appointment must be wholly before lunch or start at/after lunch ends. |
| `lunch_start_latest` | Latest allowed lunch start. If `null`, lunch is fixed at `lunch_start`. |
| `nminutes_lunch` | Length of the lunch block. It is enforced in every table and judging room. |
| `closing_ceremony_time` | Earliest allowed closing-ceremony start. Closing cannot start until all competitive events finish and deliberation after judging is complete. |
| `closing_ceremony_time_latest` | Latest allowed closing-ceremony start. If `null`, closing is fixed at `closing_ceremony_time`. |
| `deliberation_duration` | Required time from the end of the final judging appointment to the start of closing. It may overlap table matches. |

**Very early closing time:** the default lexicographic optimizer minimizes the
competitive finish first. If `closing_ceremony_time` is extremely early, the
requested time is treated as the earliest desired closing; when it is impossible,
closing is moved to the earliest feasible time (no later than
`closing_ceremony_time_latest`). In other words, the optimizer will try to give
us the shortest schedule possible. The early value does not alter the objective
(which already prioritizes the shortest schedule), and by itself it is not a
deadline. Setting an equally early/tight
`closing_ceremony_time_latest` turns that preference into a hard deadline and can
make the model infeasible.

### `team`

| Field | What it does |
|---|---|
| `time_between_events` | Hard lower bound on each team's end-to-start gap between every pair of its five events (R1, R2, R3, Project, and Design). It cannot be negative. The three table rounds are also forced to occur in order. |

The model has a `minimum_team_gap` variable whose initial lower bound is this
value. Depending on the objective mode, it may find a schedule whose actual
minimum gap is larger.

### `solver`

| Field | What it does |
|---|---|
| `max_time_seconds` | CP-SAT time limit for **each** solve stage, not necessarily the whole run. Lexicographic mode can run three stages. |
| `num_search_workers` | Number of parallel CP-SAT search workers. |
| `random_seed` | Seed passed to CP-SAT. It affects search/reproducibility, not the validity rules. |
| `finish_allowance` | Lexicographic mode only: after the earliest finish found in stage 1, later stages may finish up to this many minutes later. `0` prevents later goals from intentionally lengthening the competitive schedule. |
| `objective_mode` | `"lexicographic"` uses strict ordered goals; `"weighted"` combines all goals into one expression. |
| `overall_finish_weight` | Weighted mode only: penalty per minute of competitive finish time. A larger value favors an earlier finish. |
| `judging_separation_weight` | Weighted mode only: reward per minute of `table_finish - judging_finish`, favoring judging that ends earlier relative to the table rounds. |
| `minimum_gap_weight` | Weighted mode only: reward per minute in the smallest team event gap. |
| `log_search_progress` | Enables OR-Tools CP-SAT search logging. It changes diagnostics, not the model. |

Lexicographic mode runs these goals in order:

1. Minimize the end time of the last competitive event.
2. Maximize `table_finish - judging_finish`, subject to the finish found in step 1 plus `finish_allowance`.
3. Maximize the smallest gap between any two events for any team, while retaining the best judging/table separation found in step 2.

Weighted mode minimizes this single expression (all terms are minutes):

```text
overall_finish_weight * competitive_finish
- judging_separation_weight * (table_finish - judging_finish)
- minimum_gap_weight * minimum_team_gap
```

## `tournament_details.json`

```json
{
  "teamlist": "teamlist.csv",
  "table_rooms": ["Table 1", "Table 2"],
  "project_rooms": ["Innovation Room 1", "Innovation Room 2"],
  "design_rooms": ["Design Room 1", "Design Room 2"]
}
```

| Field | What it does |
|---|---|
| `teamlist` | Path to the team CSV. The optimizer itself schedules anonymous team IDs, so names and travel distances do not change the CP-SAT solve. After solving, real teams are attached to those IDs: teams are sorted by `Distance`, anonymous schedules are sorted by earliest judging time, and the shortest-traveling teams receive the earliest judging schedules. A relative path is resolved relative to `tournament_details.json` when it is not found from the current working directory. |
| `table_rooms` | Display names for physical tables, in pairing order. Its length must equal `config.tournament.ntables`. |
| `project_rooms` | Display names for Project rooms. Its length must equal `config.tournament.njudging_rooms`. |
| `design_rooms` | Display names for Design rooms. Its length must equal `config.tournament.njudging_rooms`. |

All room names must be non-empty and unique across all three lists. These names
do not alter or rerun the solver; they are applied only while filling outputs.

The team CSV must contain `Team #`, `Team Name`, and numeric `Distance`; `Note` is
optional. Its row count must match the effective number of optimizer teams. For an
odd `nteams`, it may contain only the real teams; filler team `99999` is then added
automatically.

## Modular solver/template workflow

The optimizer writes an anonymous template using generic identifiers such as
`Table 1`, `Project 1`, and `Design 1`. That solution contains times, assignments,
and anonymous team IDs, but no tournament-specific room or team names.

The render-only workflow accepts that solved template plus
`tournament_details.json`. It loads the referenced `teamlist.csv`, replaces the
generic room identifiers with the ordered room names above, attaches real teams,
validates the filled schedule, and creates the operational outputs without
running OR-Tools again. The capacity counts in the solver solution and the room
name list lengths must agree.
