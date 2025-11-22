from schedule import Tournament
from utils import Event
from utils import TimeUtils
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

#  Create FLLTournament Schedule CSV
# Input: Tournament object
#        date_str - date of the tournament in MM/DD/YY format
# Output: fllt_schedule.csv file saved at fllt_schedule.csv
def create_fllt(Tournament, date_str="1/1/25"):
    def get_event_description(row):
        if row["EventName"] == "Table":
            return f"Table Round {row['RoundNo']}"
        else:
            return row["EventName"] + " Judging"
    
    events = Tournament.events.copy()
    events = events[events["EventName"].isin(["Table", "Project", "Design"])]

    # Replace all "Design" with "Robot"
    events.loc[events["EventName"] == "Design", "EventName"] = "Robot"

    # Create the FLLT columns
    events["Date"] = date_str
    events["Begin Time"] = events["Time"].apply(lambda x: x.strftime("%H:%M"))
    events["End Time"] = events.apply(lambda x: (TimeUtils.add_times(x["Time"], x["Duration"])).strftime("%H:%M"), axis=1)
    events["Type"] = events["EventName"]
    events["Round"] = events["RoundNo"].apply(lambda x: min(1, x))
    events["Description"] = events.apply(get_event_description, axis=1)    
    events["Room"] = events["Room"]
    events["Team #"] = events["Team"]
    events["Team Name"] = events["TeamName"]

    fllt_columns = [
        "Date",
        "Begin Time",
        "End Time",
        "Type",
        "Round",
        "Description",
        "Room",
        "Team #",
        "Team Name",
    ]
    fllt_events = events[fllt_columns]
    fllt_events = fllt_events.sort_values(by=["Begin Time", "Room"])
    fllt_events.to_csv("output/fllt_schedule.csv", index=False)
    print("Finished. Saved to file: output/fllt_schedule.csv")

# Utility function to create pyLaTeX Document with common settings
def create_doc(landscape=False):
    doc = Document()
    doc.packages.append(Package('geometry', options=['a4paper', 'margin=1cm', 'landscape' if landscape else "portrait"]))

    doc.packages.append(Package('xcolor', options='table'))

    return doc

# Create team schedule PDF
# Rows are each team & their events
# Input: Tournament object
# Output: team_schedule.pdf file saved as team_schedule.pdf
def create_team_schedule(Tournament):
    doc = create_doc(landscape=True)

    # doc.append(NoEscape(r'\large'))
    doc.append(NoEscape(r'\sffamily'))
    doc.append(NoEscape(r'\def\arraystretch{1.5}'))
    doc.append(NoEscape(r'\rowcolors{2}{gray!0}{gray!10}'))

    opening_ceremony_start = Tournament.config.day.start_time.strftime("%I:%M %p")
    opening_ceremony_end = TimeUtils.add_times(
        Tournament.config.day.start_time, 
        Tournament.config.day.opening_ceremony_duration
    ).strftime("%I:%M %p")

    lunch_start = Tournament.config.day.lunch_start.strftime("%I:%M %p")
    lunch_end = TimeUtils.add_times(
        Tournament.config.day.lunch_start, 
        Tournament.config.day.nminutes_lunch
    ).strftime("%I:%M %p")

    closing_ceremony_start = Tournament.config.day.closing_ceremony_time.strftime("%I:%M %p")

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
        teamnos = [tn for tn in teamnos if tn > 0]  # remove dummy teams
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
    
    doc.append("\n\nOpening Ceremony: " + opening_ceremony_start + " - " + opening_ceremony_end)
    doc.append("\nLunch: " + lunch_start + " - " + lunch_end)
    doc.append("\nClosing Ceremony: " + closing_ceremony_start + "\n\n")
    doc.append(NoEscape(r'\vspace{0.2in}'))

    doc.generate_pdf('output/team_schedule', clean_tex=False)
    print("Finished. Saved to file: team_schedule.pdf")

# Create judging schedule PDF
# Rows are time slots, columns are judging rooms
# Input: Tournament object
# Output: judging_schedule.pdf file saved as judging_schedule.pdf
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

    # Get all events in each of the judging rooms (including breaks. )
    all_judge_room_events = events[events["Room"].isin(all_rooms)]

    all_times = all_judge_room_events["Time"].unique().tolist()
    all_times.sort()

    tabular = "|c" * (1 + len(all_rooms)) + "|"

    with doc.create(Tabular(tabular)) as t:
        t.add_hline()
        t.add_row(tuple([bold("Time")] + [bold(f"{r}") for r in all_rooms]))
        t.add_hline()

        for time in all_times:
            timeevents = all_judge_room_events.groupby(by="Time").get_group(time)
            # ALL the events at this time in this room 
            roomevents = {r: 
                          timeevents[timeevents["Room"] == r].iloc[0].to_dict() for r in all_rooms}
            
            roomevent_display_items = []
            for r in all_rooms:
                if r in roomevents:
                    display_item = roomevents[r]["TeamName"]
                    if roomevents[r]["Team"] > 0:
                        display_item = f'{roomevents[r]["Team"]}: {display_item}'
                    else:
                        display_item = display_item.upper()
                else:
                    display_item = ""
                roomevent_display_items.append(display_item)

            t.add_row(
                tuple(
                    [time.strftime("%I:%M %p")] +
                    roomevent_display_items
                )
            )

            t.add_hline()
                

    doc.generate_pdf('output/judging_schedule', clean_tex=False)
    print("Finished. Saved to file: judging_schedule.pdf")


# Create referee schedule PDF
# Rows are each time slot with two teams at tables
# Input: Tournament object
# Output: ref_schedule.pdf file saved as ref_schedule.pdf
def create_ref_schedule(Tournament):
    doc = create_doc(landscape=True)

    doc.append(NoEscape(r'\large'))
    doc.append(NoEscape(r'\sffamily'))
    doc.append(NoEscape(r'\def\arraystretch{1.5}'))
    doc.append(NoEscape(r'\rowcolors{2}{gray!0}{gray!10}'))

    events = Tournament.events
    table_events = events[events["EventName"] == "Table"]
    all_tables = sorted(table_events["Room"].unique().tolist())
    all_events_at_tables = events[events["Room"].isin(all_tables)]
    times = all_events_at_tables["Time"].unique().tolist()
    times.sort()

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
            timeevents = all_events_at_tables.groupby(by="Time").get_group(time)
            teamA = timeevents.iloc[0]
            teamB = timeevents.iloc[1]

            teamA_display = f'{teamA.Team}: {teamA.TeamName}' if teamA.Team > 0 else teamA.TeamName.upper()
            teamB_display = f'{teamB.Team}: {teamB.TeamName}' if teamB.Team > 0 else teamB.TeamName.upper()

            t.add_row(tuple(
               [ time.strftime("%I:%M %p"),
                teamA.RoundNo,
                teamA.Room,
                teamA_display,
                "",
                teamB_display,
                teamB.Room]
            ))

            t.add_hline()

    doc.generate_pdf('output/ref_schedule', clean_tex=False)
    print("Finished. Saved to file: ref_schedule.pdf")