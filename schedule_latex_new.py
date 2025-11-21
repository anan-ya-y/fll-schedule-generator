from schedule_new import Tournament
from utils import Event
from pylatex.utils import NoEscape
from pylatex import (
    Document,
    Tabular,
    Package,
)

def bold(x):
    return NoEscape(r'\textbf{' + str(x) + '}')

def create_doc():
    doc = Document()
    doc.packages.append(Package('geometry', options=['a4paper', 'margin=1cm', 'landscape']))

    doc.packages.append(Package('xcolor', options='table'))

    return doc

def create_team_schedule(Tournament):
    doc = create_doc()

    # doc.append(NoEscape(r'\large'))
    doc.append(NoEscape(r'\sffamily'))
    doc.append(NoEscape(r'\def\arraystretch{1.5}'))
    doc.append(NoEscape(r'\rowcolors{2}{gray!0}{gray!10}'))

    with doc.create(Tabular("|rl|cc|cc|cc|cc|cc|")) as t:
        t.add_hline()
        t.add_row((
            bold(r'Team \#'),
            bold(r'Team Name'),
            bold(r'Round 1'),
            bold(r'Table \#'),
            bold(r'Round 2'),
            bold(r'Table \#'),
            bold(r'Round 3'),
            bold(r'Table \#'),
            bold(r'Project'),
            bold(r'Room \#'),
            bold(r'Robot Design'),
            bold(r'Room \#'),
        ))
        t.add_hline()
        teamnos = list(Tournament.events_by_team.keys())
        teamnos.sort(key=lambda x: int(x))
        for teamno in teamnos:
            teamevents = Tournament.events_by_team[teamno]
            teamname = f"Team {teamno}"

            team = {}
            for event in teamevents:
                team[event.title] = (event.time, event.room, event.duration)

            r1_time, r1_table, _ = team["Round 1"] if "Round 1" in team else ("x", "x", None)
            r2_time, r2_table, _ = team["Round 2"] if "Round 2" in team else ("x", "x", None)
            r3_time, r3_table, _ = team["Round 3"] if "Round 3" in team else ("x", "x", None)
            project_time, project_room, _ = team["Project"] if "Project" in team else ("x", "x", None)
            design_time, design_room, _ = team["Design"] if "Design" in team else ("x", "x", None)

            t.add_row((teamno,
                       teamname,
                       r1_time.strftime("%I:%M %p") if r1_time != "x" else "x",
                       r1_table,
                       r2_time.strftime("%I:%M %p") if r2_time != "x" else "x",
                       r2_table,
                       r3_time.strftime("%I:%M %p") if r3_time != "x" else "x",
                       r3_table,
                       project_time.strftime("%I:%M %p") if project_time != "x" else "x",
                       project_room,
                       design_time.strftime("%I:%M %p") if design_time != "x" else "x",
                       design_room))
            t.add_hline()

    doc.generate_pdf('team_schedule', clean_tex=False)


