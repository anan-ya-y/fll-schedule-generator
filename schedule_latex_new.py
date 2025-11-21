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

        teamnos = Tournament.teamid_keys.copy()
        teamnos.sort(key=lambda x: int(x))
        for teamno in teamnos:
            teamevents = Tournament.get_events_by_team().get_group(teamno)
            strevents = {
                "Project": ("XX:XX", "Room X"), 
                "Design": ("XX:XX", "Room X"),
                "Round 1": ("XX:XX", "Table X"),
                "Round 2": ("XX:XX", "Table X"),
                "Round 3": ("XX:XX", "Table X"),
            }

            for te in teamevents.itertuples():
                if te.RoundNo == 0:
                    strevents[te.EventName] = (te.Time.strftime("%I:%M %p"), te.Room)
                else:
                    strevents[f"Round {te.RoundNo}"] = (te.Time.strftime("%I:%M %p"), te.Room)
            teamname = Tournament.config.team.teamnos_to_names[int(teamno)]

            t.add_row((teamno,
                       teamname,
                       strevents["Round 1"][0],
                       strevents["Round 1"][1],
                       strevents["Round 2"][0],
                       strevents["Round 2"][1],
                       strevents["Round 3"][0],
                       strevents["Round 3"][1],
                       strevents["Project"][0],
                       strevents["Project"][1],
                       strevents["Design"][0], 
                       strevents["Design"][1],))
            t.add_hline()

    doc.generate_pdf('team_schedule', clean_tex=False)


