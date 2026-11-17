from __future__ import annotations

import json
from pathlib import Path

from schedule import Tournament


def _minutes(value) -> int:
    return value.hour * 60 + value.minute


def _team_colors(index: int, count: int) -> dict[str, str]:
    # Sweep most of the color wheel without duplicating the first hue at the end.
    hue = (215 + index * 300 / max(count, 1)) % 360
    return {
        "light": f"hsl({hue:.1f} 78% 82%)",
        "dark": f"hsl({hue:.1f} 48% 29%)",
        "border": f"hsl({hue:.1f} 68% 43%)",
    }


def create_all_rooms_schedule(
    tournament: Tournament,
    output_folder: str | Path,
) -> Path:
    """Create a standalone, zoomable timeline containing every event room."""
    events = tournament.events.sort_values(["Time", "Room"], kind="stable")
    configured_rooms = (
        tournament.config.tournament.table_names
        + tournament.config.tournament.project_room_names
        + tournament.config.tournament.design_room_names
    )
    rooms = list(dict.fromkeys(configured_rooms + events["Room"].tolist()))
    table_rooms = set(tournament.config.tournament.table_names)
    start_minute = (min(_minutes(value) for value in events["Time"]) // 30) * 30
    end_minute = max(
        _minutes(row.Time) + int(row.Duration)
        for row in events.itertuples(index=False)
    )
    end_minute = ((end_minute + 29) // 30) * 30

    real_teams = sorted(
        int(value)
        for value in events["Team"].unique()
        if int(value) > 0
    )
    colors = {
        team: _team_colors(index, len(real_teams))
        for index, team in enumerate(real_teams)
    }
    event_data = []
    for row in events.itertuples(index=False):
        team_number = int(row.Team)
        label = (
            f"{team_number}: {row.TeamName}"
            if team_number > 0
            else str(row.TeamName).upper()
        )
        event_data.append(
            {
                "room": str(row.Room),
                "start": _minutes(row.Time),
                "duration": int(row.Duration),
                "event": str(row.EventName),
                "round": int(row.RoundNo),
                "team": team_number,
                "teamName": "" if team_number <= 0 else str(row.TeamName),
                "label": label,
                "color": colors.get(team_number),
            }
        )

    destination = Path(output_folder) / "all_rooms_schedule.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(event_data, separators=(",", ":")).replace("</", "<\\/")
    room_payload = json.dumps(rooms).replace("</", "<\\/")
    table_room_payload = json.dumps(sorted(table_rooms)).replace("</", "<\\/")
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>All rooms schedule</title>
<style>
:root {{ color-scheme:light dark; --bg:#f7f8fa; --panel:#fff; --text:#172033; --muted:#5c667a; --line:#d9deea; --break:#fef3c7; --lunch:#fee2e2; --highlight:#f97316; }}
@media (prefers-color-scheme:dark) {{ :root {{ --bg:#111827; --panel:#1f2937; --text:#f3f4f6; --muted:#b4bdcc; --line:#455064; --break:#5a4715; --lunch:#612b31; --highlight:#fb923c; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:14px/1.3 system-ui,sans-serif; }}
header {{ padding:16px 20px 12px; background:var(--panel); border-bottom:1px solid var(--line); }}
h1 {{ margin:0 0 10px; font-size:22px; font-weight:600; }}
.controls {{ display:flex; flex-wrap:wrap; gap:16px; align-items:end; }}
label {{ display:grid; gap:4px; color:var(--muted); font-size:12px; }}
input,select {{ min-height:36px; padding:6px 9px; color:var(--text); background:var(--panel); border:1px solid var(--line); border-radius:6px; font:inherit; }}
input[type="range"] {{ width:190px; padding:0; }}
.zoom-scale {{ display:flex; align-items:center; gap:8px; color:var(--muted); font-size:12px; }}
.shell {{ height:calc(100vh - 140px); min-height:520px; overflow:auto; position:relative; }}
.grid {{ display:grid; position:relative; }}
.corner,.room-head {{ position:sticky; top:0; z-index:5; min-height:56px; display:flex; align-items:center; justify-content:center; padding:8px; background:var(--panel); border-right:1px solid var(--line); border-bottom:1px solid var(--line); font-weight:600; text-align:center; }}
.corner {{ left:0; z-index:7; }}
.axis {{ position:sticky; left:0; z-index:4; background:var(--panel); border-right:1px solid var(--line); }}
.time-label {{ position:absolute; right:8px; transform:translateY(-50%); color:var(--muted); font-size:12px; white-space:nowrap; }}
.room-column {{ position:relative; border-right:1px solid var(--line); background-image:repeating-linear-gradient(to bottom, transparent 0, transparent calc(var(--half-hour) - 1px), var(--line) calc(var(--half-hour) - 1px), var(--line) var(--half-hour)); }}
.event {{ position:absolute; left:4px; right:4px; overflow:hidden; padding:4px 7px; border:0; border-left:4px solid var(--line); border-radius:5px; color:var(--text); text-align:left; font:inherit; line-height:1.15; background:var(--panel); }}
.event.team-event {{ background:var(--team-light); border-left-color:var(--team-border); color:#172033; }}
@media (prefers-color-scheme:dark) {{ .event.team-event {{ background:var(--team-dark); color:#f8fafc; }} }}
.event[data-type="Break"] {{ background:var(--break); }} .event[data-type="Lunch"] {{ background:var(--lunch); }}
.event.compact {{ display:flex; align-items:center; gap:8px; white-space:nowrap; }}
.event.dim {{ opacity:.14; }} .event.match {{ outline:3px solid var(--highlight); outline-offset:-2px; opacity:1; }}
.event-time {{ display:block; color:currentColor; opacity:.72; font-size:11px; white-space:nowrap; }}
.event-label {{ font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.event-kind {{ color:currentColor; opacity:.7; font-size:11px; }}
#details {{ min-height:28px; padding:6px 20px; background:var(--panel); border-top:1px solid var(--line); color:var(--muted); }}
</style>
</head>
<body>
<header>
  <h1>All rooms schedule</h1>
  <div class="controls">
    <label>Find team <input id="team-filter" placeholder="number or name"></label>
    <label>Vertical zoom <span class="zoom-scale"><span>Small</span><input id="zoom" type="range" min="3.25" max="7" step="0.25" value="4" aria-label="Vertical zoom"><span>Large</span></span></label>
  </div>
</header>
<main class="shell" id="shell"><div class="grid" id="grid" aria-label="All tournament rooms timeline"></div></main>
<div id="details" aria-live="polite">Select an event for details.</div>
<script>
const rooms={room_payload}; const tableRooms=new Set({table_room_payload}); const events={payload}; const dayStart={start_minute}; const dayEnd={end_minute};
const grid=document.getElementById('grid'), details=document.getElementById('details'), filter=document.getElementById('team-filter'), zoom=document.getElementById('zoom');
function clock(value){{const h=Math.floor(value/60)%24,m=value%60,s=h<12?'AM':'PM',d=(h%12)||12;return `${{d}}:${{String(m).padStart(2,'0')}} ${{s}}`;}}
function setColors(element,color){{if(!color)return;element.style.setProperty('--team-light',color.light);element.style.setProperty('--team-dark',color.dark);element.style.setProperty('--team-border',color.border);}}
function render(){{const px=Number(zoom.value),height=(dayEnd-dayStart)*px;grid.innerHTML='';const columns=['80px',...rooms.map(room=>tableRooms.has(room)?'minmax(290px,1.35fr)':'minmax(220px,1fr)')];grid.style.gridTemplateColumns=columns.join(' ');grid.style.minWidth=`${{80+rooms.reduce((sum,room)=>sum+(tableRooms.has(room)?290:220),0)}}px`;grid.style.setProperty('--half-hour',`${{30*px}}px`);grid.append(Object.assign(document.createElement('div'),{{className:'corner',textContent:'Time'}}));rooms.forEach(room=>grid.append(Object.assign(document.createElement('div'),{{className:'room-head',textContent:room}})));const axis=document.createElement('div');axis.className='axis';axis.style.height=`${{height}}px`;for(let t=dayStart;t<=dayEnd;t+=30){{const mark=document.createElement('span');mark.className='time-label';mark.style.top=`${{(t-dayStart)*px}}px`;mark.textContent=clock(t);axis.append(mark);}}grid.append(axis);rooms.forEach(room=>{{const col=document.createElement('div');col.className='room-column';col.style.height=`${{height}}px`;events.filter(e=>e.room===room).forEach(e=>{{const button=document.createElement('button'),time=document.createElement('span'),label=document.createElement('span'),kind=document.createElement('span');button.type='button';button.className=`event ${{e.team>0?'team-event':''}} ${{e.duration<=10?'compact':''}}`;button.dataset.type=e.event;button.dataset.team=String(e.team);button.dataset.search=`${{e.team}} ${{e.teamName}}`.toLowerCase();button.style.top=`${{(e.start-dayStart)*px}}px`;button.style.height=`${{Math.max(e.duration*px-2,24)}}px`;setColors(button,e.color);time.className='event-time';time.textContent=e.duration<=10?clock(e.start):`${{clock(e.start)}}-${{clock(e.start+e.duration)}}`;label.className='event-label';label.textContent=e.label;kind.className='event-kind';kind.textContent=e.round?`R${{e.round}}`:e.event;button.append(time,label,kind);button.addEventListener('click',()=>details.textContent=`${{room}} · ${{e.event}}${{e.round?` Round ${{e.round}}`:''}} · ${{clock(e.start)}}-${{clock(e.start+e.duration)}} · ${{e.label}}`);col.append(button);}});grid.append(col);}});applyFilters();}}
function applyFilters(){{const query=filter.value.trim().toLowerCase();document.querySelectorAll('.event').forEach(event=>{{const matches=!query||event.dataset.search.includes(query);event.classList.toggle('dim',!matches);event.classList.toggle('match',!!query&&matches);}});}}
zoom.addEventListener('input',render);filter.addEventListener('input',applyFilters);render();
</script>
</body>
</html>
"""
    destination.write_text(document, encoding="utf-8")
    print(f"Finished. Saved to file: {destination}")
    return destination
