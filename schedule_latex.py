from schedule import Schedule
from pylatex.utils import NoEscape
from pylatex import (
    Document,
    Tabular,
    Package,
)

def create_team_schedule(schedule):
    doc = Document()
    doc.packages.append(Package('geometry', options=['a4paper', 'margin=1cm', 'landscape']))

    doc.packages.append(Package('xcolor', options='table'))

    doc.append(NoEscape(r'\large'))
    doc.append(NoEscape(r'\sffamily'))
    doc.append(NoEscape(r'\def\arraystretch{1.5}'))
    doc.append(NoEscape(r'\rowcolors{2}{gray!0}{gray!10}'))

    with doc.create(Tabular("|rl|cc|cc|cc|cc|cc|")) as t:
        t.add_hline()
        t.add_row((
            NoEscape(r'\textbf{Team \#}'),
            NoEscape(r'\textbf{Team Name}'),
            NoEscape(r'\textbf{Round 1}'),
            NoEscape(r'\textbf{Table \#}'),
            NoEscape(r'\textbf{Round 2}'),
            NoEscape(r'\textbf{Table \#}'),
            NoEscape(r'\textbf{Round 3}'),
            NoEscape(r'\textbf{Table \#}'),
            NoEscape(r'\textbf{Project}'),
            NoEscape(r'\textbf{Room \#}'),
            NoEscape(r'\textbf{Robot Design}'),
            NoEscape(r'\textbf{Room \#}'),
        ))
        t.add_hline()
        teamnos = list(schedule.events_by_team.keys())
        teamnos.sort(key=lambda x: int(x))
        for teamno in teamnos:
            team = schedule.events_by_team[teamno]
            teamname = f"Team {teamno}"
            r1_time, r1_table, _ = team["Round 1"]
            r2_time, r2_table, _ = team["Round 2"]
            r3_time, r3_table, _ = team["Round 3"]
            project_time, project_room, _ = team["P"]
            design_time, design_room, _ = team["RD"]

            t.add_row((teamno,
                       teamname,
                       r1_time.strftime("%I:%M %p"),
                       r1_table,
                       r2_time.strftime("%I:%M %p"),
                       r2_table,
                       r3_time.strftime("%I:%M %p"),
                       r3_table,
                       project_time.strftime("%I:%M %p"),
                       project_room,
                       design_time.strftime("%I:%M %p"),
                       design_room))
            t.add_hline()

    doc.generate_pdf("team_schedule", clean_tex=False)
