from schedule import Tournament
from utils import Event
import pandas as pd
from pylatex.utils import NoEscape
from pylatex import (
    Document,
    Tabular,
    Package,
    LongTable,
)

def bold(x):
    return NoEscape(r'\textbf{' + str(x) + '}')

def create_doc(landscape=False):
    doc = Document()
    doc.packages.append(Package('geometry', options=['a4paper', 'margin=1cm', 'landscape' if landscape else "portrait"]))

    doc.packages.append(Package('xcolor', options='table'))

    return doc

def create_team_schedule(Tournament):
    doc = create_doc(landscape=True)

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

        teamnos = Tournament.events["Team"].unique().tolist()
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

def create_judging_schedule(Tournament):
    doc = create_doc(landscape=True)

    doc.append(NoEscape(r'\large'))
    doc.append(NoEscape(r'\sffamily'))
    doc.append(NoEscape(r'\def\arraystretch{1.5}'))
    doc.append(NoEscape(r'\rowcolors{2}{gray!0}{gray!10}'))

    events = Tournament.events
    project_events = events[events["EventName"] == "Project"]
    design_events = events[events["EventName"] == "Design"]
    judging_events = pd.concat([project_events, design_events])
    all_rooms = sorted(judging_events["Room"].unique().tolist())

    all_times = judging_events["Time"].unique().tolist()
    all_times.sort()

    tabular = "|c" * (1 + len(all_rooms)) + "|"

    with doc.create(Tabular(tabular)) as t:
        t.add_hline()
        t.add_row(tuple([bold("Time")] + [bold(f"{r}") for r in all_rooms]))
        t.add_hline()

        for time in all_times:
            timeevents = judging_events.groupby(by="Time").get_group(time)
            roomevents = {r: 
                          timeevents[timeevents["Room"] == r].iloc[0].to_dict() for r in all_rooms}
            t.add_row(
                tuple(
                    [time.strftime("%I:%M %p")] +
                    [f'{roomevents[r]["Team"]}: {roomevents[r]["TeamName"]}' if r in roomevents else "" for r in all_rooms]
                )
            )

            t.add_hline()
                

    doc.generate_pdf('judging_schedule', clean_tex=False)

def create_ref_schedule(Tournament):
    doc = create_doc(landscape=True)

    doc.append(NoEscape(r'\large'))
    doc.append(NoEscape(r'\sffamily'))
    doc.append(NoEscape(r'\def\arraystretch{1.5}'))
    doc.append(NoEscape(r'\rowcolors{2}{gray!0}{gray!10}'))

    events = Tournament.events
    match_events = events[events["RoundNo"] != 0].sort_values(by=["Time", "Room"])
    match_events = match_events.groupby(by=["Time"])
    times = match_events.groups.keys()

    with doc.create(LongTable("|c|c|l|l|p{3in}|r|r|")) as t:
        t.add_hline()
        t.add_row((
            bold("Time"),
            bold("Rnd"),
            bold("Table No."),
            bold("Team 1"),
            bold("Notes"),
            bold("Team 2"),
            bold("Table No.")
        ))
        t.add_hline()

        for time in times:
            timeevents = match_events.get_group(time)
            teamA = timeevents.iloc[0]
            teamB = timeevents.iloc[1]

            t.add_row(tuple(
               [ time.strftime("%I:%M %p"),
                teamA.RoundNo,
                teamA.Room,
                f'{teamA.Team}: {teamA.TeamName}',
                "",
                f'{teamB.Team}: {teamB.TeamName}',
                teamB.Room]
            ))

            t.add_hline()

    doc.generate_pdf('ref_schedule', clean_tex=False)