# FLL Schedule Printout Compatibility Specification

## 1. Scope and source of truth

This document specifies the six schedule artifacts intended by the repository's
`main` branch at commit `a5ff48abd288b433aad047bb2afc11fdc3cf9b11`
(2026-10-04). It describes the observable content and presentation rules so that
another implementation can generate compatible outputs without using Python,
Pandas, PyLaTeX, or LaTeX.

The intended artifact catalog is:

1. `fllt_schedule.csv`
2. `emcee_schedule.pdf`
3. `judging_schedule.pdf`
4. `ref_schedule.pdf`
5. `team_schedule.pdf`
6. `room_schedule.pdf`

As of the referenced commit, the command-line program generates only
`fllt_schedule.csv` and `emcee_schedule.pdf` from this catalog; calls for the other
four PDFs are commented out. Each PDF renderer also preserves a same-named `.tex`
source file. The current workflow writes `config_generated.json` in the selected
output directory and, when it creates a new schedule rather than loading a template,
writes a timestamped `tournament_schedule_template_*.csv`. The CLI's message saying
that six output files should exist is therefore not an accurate statement of
current runtime behavior.

This specification has two kinds of requirements:

- **Compatibility requirement**: behavior needed to reproduce the current output.
- **Recommended hardening**: behavior a replacement should adopt where the current
  renderer is ambiguous, fragile, or tied to a two-table tournament. Hardening
  choices should be confirmed if byte-for-byte or visual regression compatibility
  is required.

## 2. Canonical input model

All six artifacts are views of one normalized event collection. An event has:

| Field | Type | Meaning |
|---|---|---|
| `Time` | local time | Event start time, with no date or timezone |
| `EventName` | string | Normally `Table`, `Project`, `Design`, `Break`, or `Lunch` |
| `RoundNo` | integer | Table round number; `0` for judging, breaks, and lunch |
| `Room` | string | Display-ready room or table name |
| `Duration` | integer | Duration in minutes |
| `Team` | integer | Actual team number, or a negative sentinel |
| `TeamName` | string | Display-ready team name, or event name for a break/lunch row |
| `Note` | string | Optional team note used only by the emcee schedule |

Team sentinel values are:

- `-1`: unassigned slot; valid templates must not reach final output with these.
- `-2`: no team, used for breaks and lunch.
- `99999`: filler/dummy team used when an odd-sized team list fills an even-sized
  template.

The source template initially uses internal team IDs. Before rendering, those IDs
are replaced with actual team numbers and retained separately as `Team ID`.
Renderers use the actual `Team` value, not `Team ID`.

Additional tournament metadata required by the printouts is:

| Field | Used by |
|---|---|
| Tournament date string | FLLTournament CSV |
| Day start time | Team schedule opening ceremony |
| Opening ceremony duration | Team schedule |
| Lunch start and duration | Team schedule |
| Closing ceremony start time | Team schedule |
| Team-number-to-name mapping | Team schedule |
| Project and design room lists/names | All judging views |

The team list must provide `Team #`, `Team Name`, and `Distance`; `Note` is
optional. Room names supplied in tournament details replace the template names
`P1`, `P2`, ... and `D1`, `D2`, ... before rendering.

## 3. Shared presentation rules

Unless an individual artifact overrides a rule:

- PDF page size is A4 with 1 cm margins.
- Typeface is sans serif.
- Table row height is approximately 1.5 times the normal row height.
- Body rows alternate white and 10% gray, beginning with white on the second
  LaTeX table row.
- Every table has vertical borders, a border above and below the header, and a
  horizontal rule after every data row.
- Display times use a 12-hour clock with a two-digit hour and minute plus uppercase
  `AM`/`PM`, for example `09:30 AM` and `01:08 PM`.
- No PDF includes a tournament title, tournament date, page number, logo, generated
  timestamp, or explicit timezone.
- Room names, team names, team numbers, and notes are displayed as supplied unless
  a printout-specific rule says otherwise.

PDF filenames are fixed and are written under the requested output folder. A
replacement may use any PDF technology, but the visible result should follow this
specification.

## 4. `fllt_schedule.csv`

### Purpose

Machine-readable import file for FLLTournament (FLLT). This is not intended as a
human printout.

### Inclusion and transformation rules

1. Start with all events.
2. Keep only events whose `EventName` is exactly `Table`, `Project`, or `Design`.
3. Exclude events whose actual team number is `99999`.
4. Rename event type `Design` to `Robot`.
5. Do not include breaks, lunch, ceremonies, notes, durations as a separate field,
   or internal team IDs. Unassigned slots are not explicitly filtered, so upstream
   validation must ensure that no retained event has team `-1`.

### Exact column contract

Columns must appear in this order:

| Column | Derivation |
|---|---|
| `Date` | Tournament date argument, copied verbatim to every row |
| `Begin Time` | Start time formatted as 24-hour `HH:MM` |
| `End Time` | Start time plus `Duration` minutes, formatted as 24-hour `HH:MM` |
| `Type` | `Table`, `Project`, or mapped value `Robot` |
| `Round` | `max(1, RoundNo)`; judging therefore uses round `1` |
| `Description` | `Table Round N` for table events; otherwise `Project Judging` or `Robot Judging` |
| `Room` | Event room copied as displayed |
| `Team #` | Actual team number |
| `Team Name` | Actual team name |

Rows are sorted ascending by the formatted `Begin Time`, then ascending by `Room`.
Because `Begin Time` is zero-padded 24-hour text, this is chronologically correct
within one day. CSV output includes a header row and no index column.

### Acceptance checks

- A non-dummy team with three table rounds and two judging sessions produces five
  CSV rows.
- No row has type `Design`.
- No row contains team `99999`, `Break`, or `Lunch`.
- Every row has exactly nine fields in the specified order.

## 5. `team_schedule.pdf`

### Purpose

One-line summary per team for distribution to teams and event staff.

### Page and table

- Landscape A4.
- One 12-column table, using normal document font size. Team number is right
  aligned, team name is left aligned, and the other ten columns are centered.
- Fixed header sequence:

| Pair | Columns |
|---|---|
| Identity | `Team #`, `Team Name` |
| Match 1 | `Round 1`, `Table #` |
| Match 2 | `Round 2`, `Table #` |
| Match 3 | `Round 3`, `Table #` |
| Project judging | `Project`, `Room #` |
| Robot design judging | `Robot Design`, `Room #` |

### Row rules

- Include one row for every unique actual team number greater than zero, excluding
  `99999`.
- Sort rows by team number numerically ascending.
- `Team Name` comes from the team-number-to-name mapping.
- Each match cell contains the event start time; the following cell contains the
  table/room string.
- The Project and Robot Design cells contain their start time, followed by their
  judging room string.
- Compatibility behavior assumes exactly three table rounds numbered 1, 2, and 3,
  one Project event, and one Design event per team.
- If one of those five events is absent, the current renderer leaves placeholder
  text: `XX:XX` and `Room X` or `Table X`.

### Footer

After the table, print these lines in this order:

1. `Opening Ceremony: <start> - <end>`
2. `Lunch: <start> - <end>`
3. `Closing Ceremony: <start>`

Opening end is start plus opening duration. Lunch end is lunch start plus lunch
duration. Closing ceremony duration is not displayed.

### Limitations to resolve in a replacement

- The table is not designed to split cleanly across pages and has no repeated
  header behavior.
- The schema is fixed to three rounds rather than driven by the configured number
  of table rounds.
- There is no title or date to distinguish printouts from different tournaments.

For strict compatibility, retain these behaviors. For a hardened replacement,
make the round columns dynamic, repeat headers on additional pages, and decide
whether title/date should be added.

## 6. `judging_schedule.pdf`

### Purpose

Master matrix for judging operations: times down the page and judging rooms across
the page.

### Page and table

- Landscape A4.
- Large font.
- First column header is `Time`.
- Remaining columns are all rooms that host a `Project` or `Design` event, sorted
  lexicographically by displayed room name.
- Each room header is `<room> (P)` if that room appears in a Project event;
  otherwise it is `<room> (D)`.

### Row and cell rules

- After identifying judging rooms, include **all events** occurring in those rooms,
  not only judging events. This intentionally brings room breaks and lunch into the
  matrix.
- Create one row for each distinct start time across those room events, sorted
  chronologically ascending.
- Format the first cell as a 12-hour display time.
- For a positive team number, display `<team number>: <team name>`.
- For a zero or negative team number, display `TeamName` converted to uppercase;
  generated breaks therefore display `BREAK` and lunch displays `LUNCH`.
- If a room has no event at a displayed time, the intended cell value is blank.

### Current compatibility hazard

The existing implementation attempts to select the first event for every room at
every listed time before it checks whether an event exists. It therefore crashes
instead of producing a blank cell when judging-room timelines are not synchronized.
The checked-in schedule works because all judging slots, breaks, and lunch are
synchronized across all judging rooms.

A replacement should implement the intended blank-cell behavior unless reproducing
this failure is explicitly required. If more than one event exists in the same room
at the same start time, compatibility behavior uses the first event in input order.

## 7. `room_schedule.pdf`

### Purpose

Door or room sheets: one large-format schedule page for each judging room.

### Page structure

- Portrait A4.
- Huge font.
- One judging room per page.
- Judging room order is first appearance after concatenating all Project events
  followed by all Design events; it is not explicitly sorted. In normal data this
  places Project rooms before Design rooms.
- Page heading is `<room> (Project)` for a room that hosts Project judging;
  otherwise `<room> (Design)`.
- Insert a page break between rooms, but not after the final room.

### Table and row rules

Each page has a three-column table with headers `Time`, `Team #`, and `Team Name`.

- Include all events in the room, including judging, breaks, and lunch.
- Sort distinct start times chronologically.
- At each start time, emit one row per event at that time, preserving event order.
- Positive team: show its team number and team name.
- Zero or negative team: leave `Team #` blank and show uppercase `TeamName`.
- Unlike the FLLT and team schedules, the current renderer does not exclude dummy
  team `99999`; because it is positive, it is shown as a normal team.

## 8. `ref_schedule.pdf`

### Purpose

Chronological field schedule for referees. It shows the two teams playing at each
match time and includes table breaks and lunch.

### Page and table

- Landscape A4.
- Large font.
- A multi-page-capable table with seven columns:

| Column | Header | Content |
|---|---|---|
| 1 | `Time` | Start time |
| 2 | `Rnd` | Round number from the first table event |
| 3 | `Table No.` | First table name |
| 4 | `Team 1` | First team/event display |
| 5 | `Notes` | Blank whitespace |
| 6 | `Team 2` | Second team/event display |
| 7 | `Table No.` | Second table name |

The Notes column has a fixed approximate width of 2.5 inches. Team 1 is left
aligned and Team 2 is right aligned.

### Row and cell rules

- Identify table rooms from events whose `EventName` is `Table`.
- Include all events occurring in those rooms, thereby including table breaks and
  lunch.
- Create one row for each active configured table pair at each distinct start
  time, sorted chronologically and then by pair order.
- Tables are paired in configuration order: the first two table names form one
  pair, the next two form another pair, and so on. The first table in the pair
  becomes Team 1 and the second becomes Team 2.
- Within every round, matches visit those pairs in configuration order and cycle
  back to the first pair after the last pair.
- Positive team display is `<team number>: <team name>`.
- Zero or negative team display is uppercase `TeamName`, normally `BREAK` or
  `LUNCH`.
- The round value is taken from the first event; breaks and lunch display `0`.
- Dummy team `99999` is not filtered and is shown as a normal team.

### Table-pair validation

The renderer supports any even number of configured tables. It requires both
members of an active pair to have an event at the same time and rejects incomplete
or cross-pair rows.

Although a long-table mechanism is used, the current document does not explicitly
repeat the header on later pages.

## 9. `emcee_schedule.pdf`

### Purpose

The referee schedule plus team-specific notes for the announcer/emcee.

### Shared behavior with referee schedule

Page format, columns, event inclusion, time ordering, table-pair ordering, team
display, break/lunch display, round values, dummy-team handling, and multi-table
pairing are identical to `ref_schedule.pdf`.

### Notes column

The only visible difference from the referee schedule is column 5:

- Render in a very small font.
- Place Team 1's note at the left edge.
- Place Team 2's note at the right edge on the same line.
- Missing notes should display as empty text.

The current implementation inserts notes into raw LaTeX without escaping. Notes
containing characters such as `&`, `%`, `$`, `#`, `_`, `{`, `}`, `~`, `^`, or `\`
can corrupt rendering or alter the document. A replacement must treat notes as
plain text and escape them for its output technology.

If a `Note` column exists but the synthesized dummy team has no note, the current
data path can display the literal missing-value representation (`nan`). A hardened
replacement should normalize null notes to an empty string.

## 10. Cross-artifact consistency requirements

For any non-dummy team:

- Team number and team name must be identical in all artifacts.
- Each FLLT Table row must correspond to the same time and table in the team,
  referee, and emcee schedules.
- Each FLLT Project/Robot row must correspond to the same time and room in the team,
  judging, and room schedules.
- `Design` is renamed to `Robot` only in FLLT and to the label `Robot Design` in the
  team schedule. Judging-room headings use `Design` or `(D)`.
- Break and lunch rows appear only in operational PDFs (judging, room, referee,
  emcee), never in FLLT or the per-team table.
- The configured lunch interval shown in the team footer must agree with the lunch
  event start and duration shown in operational schedules.

## 11. Minimum acceptance test fixture

A replacement should be tested with at least:

- four table rooms arranged as two physical pairs (plus a two-table regression
  case);
- one Project room and one Design room;
- two real teams plus one dummy-team case in a separate test;
- three table rounds per real team;
- one Project and one Design event per real team;
- a synchronized judging break;
- a table break;
- lunch in every room;
- one team with a note and one with an empty note;
- team/room/note text containing output-special characters.

Verify:

1. Exact CSV headers, field derivations, filters, and ordering.
2. Correct 24-hour CSV time format and 12-hour PDF time format.
3. Dummy exclusion from FLLT and team schedule, plus the chosen policy for the
   remaining PDFs.
4. Correct labels for Design/Robot/Robot Design.
5. Correct uppercase and blank-team-number treatment for breaks and lunch.
6. Consistent team-event assignments across all six artifacts.
7. Multi-page behavior with enough teams/time slots to overflow one page.
8. Correct pair rows when more than two table events share a break or lunch time.

## 12. Decisions needed for a new implementation

The following are implementation-policy choices rather than reliable business
rules in the current code:

1. Whether to keep the PDFs visually minimal or add tournament name, date, and page
   numbering.
2. Whether team schedules must support a configurable number of match rounds.
3. Whether judging-room matrices permit unsynchronized rooms with blank cells.
4. Whether dummy team `99999` should be removed from every human-facing printout.
5. Whether repeated headers are required on multi-page tables.
6. How long names and notes should wrap, truncate, or reduce in size.

Unless those policies are deliberately changed, use the compatibility behavior in
the artifact sections above.
