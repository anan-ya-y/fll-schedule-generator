from utils import TimeUtils, Event
import numpy as np
import pandas as pd

class Tournament:
    def __init__(self, config):
        self.config = config
        self.events = pd.DataFrame(columns=[
            "Time", "EventName", "RoundNo", "Room", "Duration", "Team"
        ])
        # EventName = "Project", "Design", "Round 1", "Round 2", "Round 3", "Opening/Closing/etc"
        # RoundNo = 0 if not a table round, else 1, 2, or 3



        # self.events = [] # All events in the tournament
        # self.events_by_team = {} # {teamno : [Events]}
        self.nteams = self.config.tournament.nteams
        self.teamid_keys = [str(k) for k in range(1, 1 + self.nteams)]

        self.lunch_start = self.config.day.lunch_start
        self.lunch_end = self.config.day.lunch_end

        # Strategy: Create a template of events. 
        # Then, assign teams by distance. 
        
        # Strategy for template:
        # 1. Fix the Judging rounds
        self.get_judging_times()
        self.assign_judging()
        # 2. Match Table Round 1. 
        # 3. Match Table Round 3. 
        # 4. Match Table Round 2 - Try n times, then start over.
        
        self.verify_schedule() 

        # When a team is found, save the template. 
        # Then, create a way for us to insert the template file into the constructor. 
        # Fill in teams by distance/latest judging order. 

    # Returns the judging slots. 
    def get_judging_times(self):
        judging_start_time = TimeUtils.add_times( 
            self.config.day.opening_ceremony_end_time,
            self.config.day.judging_prep 
        )
        
        # Number of judging slots required. 
        total_judging_rooms = self.config.tournament.nproject_rooms + \
                                self.config.tournament.ndesign_rooms
        n_judging_slots = np.round((self.config.tournament.nteams * 2) / total_judging_rooms, 0).astype(int)

        judging_times = []
        next_judging_time = judging_start_time
        # create the list of judging times. 
        for i in range(1, 1 + n_judging_slots):
            start_time = next_judging_time
            judging_times.append(start_time)

            total_slot_length = self.config.judging.nminutes_judging + \
                                self.config.judging.nminutes_between_judging
            next_judging_time = TimeUtils.add_times(next_judging_time, total_slot_length)

            if i % self.config.judging.nteams_per_judging_sprint == 0:
                next_judging_time = TimeUtils.add_times(
                    next_judging_time,
                    self.config.judging.nminutes_between_judging
                )

            # # Make sure no judging runs through lunch
            if TimeUtils.contains_overlap([(self.lunch_start, self.config.day.nminutes_lunch),
                                           (next_judging_time, self.config.judging.nminutes_judging)]):
                next_judging_time = self.lunch_end

        # Add judging times to self.events
        judging_events = []
        for j_time in judging_times:
            # design rooms
            for design_room in self.config.tournament.design_room_names:
                judging_events.append({
                    "Time": j_time,
                    "EventName": "Design",
                    "RoundNo": 0,
                    "Room": design_room,
                    "Duration": self.config.judging.nminutes_judging,
                    "Team": -1
                })

            # project rooms
            for project_room in self.config.tournament.project_room_names:
                judging_events.append({
                    "Time": j_time,
                    "EventName": "Project",
                    "RoundNo": 0,
                    "Room": project_room,
                    "Duration": self.config.judging.nminutes_judging,
                    "Team": -1
                })
        self.events = pd.concat([self.events, pd.DataFrame(judging_events)], ignore_index=True)

    # Create judging assignments - update self.events and self.events_by_team
    def assign_judging(self, shuffle_teams=False):
        self.clear_judging_events()

        project_design_events = self.events[self.events["EventName"].isin(["Project", "Design"])]
        pd_events_sorted = project_design_events.sort_values(by=["EventName", "Room", "Time"], ascending=True)
        # ^ this particular order ["Room", "Time"] puts back to back times for the same room
        # looks like:
        # 0   09:45:00    Design       0  DR1       10   -1
        # 4   10:05:00    Design       0  DR1       10   -1
        # 8   10:25:00    Design       0  DR1       10   -1
        # 12  10:55:00    Design       0  DR1       10   -1
        # ...

        teamnos = self.teamid_keys.copy()
        if shuffle_teams:
            np.random.shuffle(teamnos)

        # Assign the teams to the first judging (design?) event as is (sorted by room/time)
        teamlist = teamnos.copy()
        # Do some math for the second event (project?) - depends on how "EventName" is sorted
        # first rooms were [1 11] [2 12] [3 13]... [10 20] if 20 teams. 
        # second rooms should be [5 15] [6 16] [7 17]... [4 14] if 20 teams.
        rooms = np.array(teamnos)
        rooms = rooms.reshape((self.config.tournament.njudging_rooms, -1))
        rooms = np.hstack((rooms[:, len(rooms[1])//2:], rooms[:, :len(rooms[1])//2])).reshape(-1)
        # ^ yes, there is basically magic happening here. Sorry, future me. 

        teamlist = teamlist + list(rooms)
        assert len(teamlist) == len(pd_events_sorted), "Team assignment length mismatch!"
        pd_events_sorted["Team"] = teamlist

        # Update self.events
        self.events.update(pd_events_sorted)

    # Create match times. 
    def get_match_times(self):
        pass

    #################################################
    ################### UTILITIES ###################
    #################################################
    # remove all judging events from self.events and self.events_by_team
    def clear_judging_events(self):
        # change the teamno of these columns to -1
        self.events.loc[self.events["EventName"].isin(["Project", "Design"]), "Team"] = -1

    # Remove all table events from self.events and self.events_by_team
    # roundno = -1 means all rounds
    def clear_table_events(self, roundno=-1):
        if roundno == -1:
            self.events = self.events[self.events["RoundNo"] != 0]
        else:
            self.events = self.events[self.events["RoundNo"] != roundno]

    # To get a specific team, do this.get_group(teamno)
    def get_events_by_team(self):
        self.events = self.events.sort_values(by="Time", ascending=True)
        return self.events.groupby(by="Team")
    
    def get_team_events_interval_list(self, teamno):
        df = self.get_events_by_team().get_group(teamno)
        df_td = df[["Time", "Duration"]]
        df_tuples = df_td.apply(lambda x: (x['Time'], x['Duration']), axis=1)
        return df_tuples.tolist()
    
    ##############################################################
    ################### VERIFICATION FUNCTIONS ###################
    ##############################################################

    # table_noval = True means - ignore Table-related verification
    # (e.g. see different oppoenents, see as many tables as possible)
    # It would only check if there are no overlaps & sufficient gaps.
    def verify_schedule(self, table_noval = False):
        # Verify all teams have all events!!
        # Verify no overlaps for teams
        no_overlaps = self.verify_no_team_overlaps()
        if not no_overlaps:
            print("Schedule verification failed: team overlaps found.")
            return False

        # Verify "gap" between events is >= whatever config says
        gap_ok, fail_team = self.verify_event_gap()
        if not gap_ok:
            print(f"Schedule verification failed: team {fail_team} has insufficient gap between events.")
            return False
        
        if table_noval:
            return True

        # Make sure all teams see as many tables as possible. 
        # Make sure all teams have different opponents for each table round

        # All checks passed!!
        return True 

    def verify_no_team_overlaps(self):
        for teamno in self.teamid_keys:
            # Create list of (start_time, duration) tuples
            time_blocks = self.get_team_events_interval_list(teamno)
            # Check for overlaps
            if TimeUtils.contains_overlap(time_blocks):
                print(f"Team {teamno} has overlapping events.")
                return False
        return True
    
    def verify_event_gap(self):
        for teamno in self.teamid_keys:
            time_blocks = self.get_team_events_interval_list(teamno)
            # Sort by start time
            time_blocks.sort(key=lambda x: x[0])
            for i in range(1, len(time_blocks)):
                prev_end = TimeUtils.add_times(time_blocks[i - 1][0], time_blocks[i - 1][1])
                curr_start = time_blocks[i][0]
                gap = TimeUtils.subtract_times(curr_start, prev_end)
                print(curr_start, prev_end, gap, self.config.team.time_between_events)
                if gap < self.config.team.time_between_events:
                    return False, teamno
                
        return True, -1