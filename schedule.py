from utils import TimeUtils, Event
from config import Config, SubConfig
import numpy as np
import json
import pandas as pd

class Tournament:
    # IF generating from scratch, provide:
    # config: Config object
    # strategy_randomize: "matches" or "judging"
    # 
    # IF loading from CSV, provide:
    # csvfile: path to CSV file
    # 
    # REGARDLESS OF STRATEGY, provide:
    # tournament_details_json: path to JSON file with teamlist and room names (see readme.md for format)
    # verbose: whether to print progress
    # veryverbose: whether to print detailed progress    
    def __init__(self, config=None, strategy_randomize="matches", 
                 csvfile=None, tournament_details_json="tournament_details.json", 
                 verbose=True, veryverbose=False):
        self.verbose = verbose
        self.veryverbose = veryverbose
        if self.veryverbose:
            self.verbose = True

        self.config = config if config is not None else Config()

        self.nteams = self.config.tournament.nteams
        self.teamid_keys = [k for k in range(1, 1 + self.nteams)]

        # Create/fill template (self.events)
        if csvfile is not None:
            self.load_schedule_csv(csvfile)
        else:
            # Generate the schedule template from scratch
            self.strategy_randomize = strategy_randomize

            self.events = pd.DataFrame(columns=[
                "Time", "EventName", "RoundNo", "Room", "Duration", "Team"
            ])
            # EventName = "Project", "Design", "Table", "Opening/Closing/etc"
            # RoundNo = 0 if not a table round, else 1, 2, or 3
            # Team = -1 = unassigned, -2 = break/no team

            self.lunch_start = self.config.day.lunch_start
            self.lunch_end = self.config.day.lunch_end

            self.create_template()

            # Save the events schedule to a CSV. - filename is tournament_schedule{time}.csv
            self.save_schedule_csv(f"output/tournament_schedule_template_{TimeUtils.get_current_time_str()}.csv")

        self.valid_template = self.verify_schedule(check_opponents=True, check_table_diversity=True)
        assert self.valid_template, "Template is not valid. Will not generate new documents. "

        # Read tournament details json and fill team info into template
        with open(tournament_details_json, 'r') as f:
            tournament_details = json.load(f)
        self.set_team_list(tournament_details["teamlist"])
        self.assign_teams_to_judging()
        self.set_room_names(tournament_details) 

        # Minor bug correction: Turn all items in the "teamno" column to int
        self.events["Team"] = self.events["Team"].astype(int)
    
    #################################################
    #### FOR FILLING TEMPLATE WITH TEAMS ####
    #################################################

    # Assign teams from teamlist.csv to the actual judging times. 
    def assign_teams_to_judging(self):
        all_earliest_times = [] # (earliest_time, teamno)
        
        for teamno in self.teamid_keys:
            team_events = self.get_events_by_team().get_group(teamno)
            judging_events = team_events[team_events["RoundNo"] == 0]
            judging_events = judging_events[judging_events["Team"] >= 0]  # remove breaks/no team
            judging_times = judging_events["Time"].values
            earliest_judging_time = min(judging_times)
            all_earliest_times.append((earliest_judging_time, teamno))
        
        all_earliest_times.sort(key=lambda x: x[0]) # sort by earliest judging time
        # get all teams by distance
        all_teams_to_dists = [(y, x) for x, y in zip(self.config.team.team_list["Team #"], self.config.team.team_list["Distance"])]
        all_teams_to_dists.sort(key=lambda x: x[0]) # sort by distance

        self.events["Team ID"] = self.events["Team"] 

        for x, y in zip(all_earliest_times, all_teams_to_dists):
            earliest_time, teamid = x
            dist, teamno = y

            self.events.loc[self.events["Team ID"] == teamid, "Team"] = teamno
            self.events.loc[self.events["Team ID"] == teamid, "TeamName"] = self.config.team.teamnos_to_names[teamno]
            
        break_events = self.events[self.events["Team"] == -2]
        break_events.loc[:, "TeamName"] = break_events.loc[:, "EventName"]
        self.events.update(break_events)

        return True

    def set_team_list(self, filename):
        self.config.team.team_list = pd.read_csv(filename)
        self.config.team.team_list.loc[:, "Team Name"] = self.config.team.team_list["Team Name"].str.strip()
        self.config.team.team_list.loc[:, "Distance"] = self.config.team.team_list["Distance"].astype(float)
        self.config.team.teamnos_to_names = {row["Team #"]: row["Team Name"] for _, row in self.config.team.team_list.iterrows()}

    def set_room_names(self, tournament_details):
        project_rooms = tournament_details["project_rooms"]
        design_rooms = tournament_details["design_rooms"]

        # replace all occurrences of P1, P2, ... and D1, D2, ... in self.events
        for i, room_name in enumerate(project_rooms):
            self.events.loc[self.events["Room"] == f"P{i+1}", "Room"] = room_name

        for i, room_name in enumerate(design_rooms):
            self.events.loc[self.events["Room"] == f"D{i+1}", "Room"] = room_name

    #################################################
    #### CREATE TEMPLATE TOP LEVEL FUNCTIONS ####
    #################################################

    def create_template(self):        
        # Strategy: Create a template of events. 
        # Then, assign teams by distance. 
        self.get_judging_times()
        self.get_match_times()
        
        if self.strategy_randomize == "judging":
            self.assign_all_matches()
            valid_schedule = self.verify_schedule(check_opponents=True, check_table_diversity=True)
            assert valid_schedule, "Match schedule algorithm failed!!!"
            self.assign_all_judging()

        else: # Randomize matches
            self.assign_all_judging()
            valid_schedule = self.verify_schedule(check_opponents=False, check_table_diversity=False)
            assert valid_schedule, "Judging schedule algorithm failed!!!"
            self.assign_all_matches()

        # 3. Verify the schedule (assign_all_matches already does this, but JUUST IN CASE)
        self.veryverbose = True
        valid_schedule = self.verify_schedule() 

        # Create lunch events for each room 
        self.create_lunch_events()

    # must be called after judging and match times are calculated
    # because "rooms" are not intelligently calculated. 
    def create_lunch_events(self):
        all_rooms = self.events["Room"].unique().tolist()
        lunch_events = []
        for room in all_rooms:
            lunch_events.append({
                "Time": self.lunch_start,
                "EventName": "Lunch",
                "RoundNo": 0,
                "Room": room,
                "Duration": self.config.day.nminutes_lunch,
                "Team": -2
            })
        self.events = pd.concat([self.events, pd.DataFrame(lunch_events)], ignore_index=True)

    #################################################
    #### TEMPLATE CREATION SUBFUNCTIONS ####
    #################################################
    
    ## CREATE TIME SLOTS ##

    # Add all judging slots to self.events 
    def get_judging_times(self):
        judging_start_time = TimeUtils.add_times( 
            self.config.day.opening_ceremony_end_time,
            self.config.day.judging_prep 
        )
        
        # Number of judging slots required. 
        total_judging_rooms = self.config.tournament.nproject_rooms + \
                                self.config.tournament.ndesign_rooms
        n_judging_slots = np.ceil((self.config.tournament.nteams * 2) / total_judging_rooms).astype(int)

        all_rooms = self.config.tournament.project_room_names + \
                    self.config.tournament.design_room_names

        judging_events = []
        next_judging_time = judging_start_time
        # create the list of judging times. 
        for i in range(1, 1 + n_judging_slots):
            start_time = next_judging_time
            # design rooms
            for design_room in self.config.tournament.design_room_names:
                judging_events.append({
                    "Time": start_time,
                    "EventName": "Design",
                    "RoundNo": 0,
                    "Room": design_room,
                    "Duration": self.config.judging.nminutes_judging,
                    "Team": -1
                })

            # project rooms
            for project_room in self.config.tournament.project_room_names:
                judging_events.append({
                    "Time": start_time,
                    "EventName": "Project",
                    "RoundNo": 0,
                    "Room": project_room,
                    "Duration": self.config.judging.nminutes_judging,
                    "Team": -1
                })

            total_slot_length = self.config.judging.nminutes_judging + \
                                self.config.judging.nminutes_between_judging
            next_judging_time = TimeUtils.add_times(next_judging_time, total_slot_length)

            if i % self.config.judging.nteams_per_judging_sprint == 0:
                judging_events.extend([{
                    "Time": next_judging_time,
                    "EventName": "Break", 
                    "RoundNo": 0, 
                    "Room": room, 
                    "Duration": self.config.judging.nminutes_between_judging,
                    "Team": -2
                } for room in all_rooms])
                next_judging_time = TimeUtils.add_times(
                    next_judging_time,
                    self.config.judging.nminutes_between_judging
                )

            # # Make sure no judging runs through lunch
            if TimeUtils.contains_overlap([(self.lunch_start, self.config.day.nminutes_lunch),
                                           (next_judging_time, self.config.judging.nminutes_judging)]):
                next_judging_time = self.lunch_end

        self.events = pd.concat([self.events, pd.DataFrame(judging_events)], ignore_index=True)

        # Create match times. 
    
    # Add all match slots to self.events
    def get_match_times(self):
        nrounds = self.config.tournament.ntable_rounds
        nmatches_per_round = np.ceil(self.nteams / self.config.tournament.ntables).astype(int)

        match_events = []
        round_no = 1
        next_match_time = self.config.day.matches_start_time
        for i in range(1, 1 + (nmatches_per_round * nrounds)):
            start_time = next_match_time 
            match_duration = self.config.table.nminutes_table_rnd1 if round_no == 1 else \
                             self.config.table.nminutes_table_allrounds
            # create events for all tables at this time
            for tableno in range(1, 1 + self.config.tournament.ntables):
                match_events.append({
                    "Time": start_time,
                    "EventName": f"Table",
                    "RoundNo": round_no,
                    "Room": f"Table {tableno}",
                    "Duration": match_duration,
                    "Team": -1
                })

            next_match_time = TimeUtils.add_times(
                next_match_time,
                match_duration
            )

            # make sure nothing runs through lunch
            if TimeUtils.contains_overlap([(self.lunch_start, self.config.day.nminutes_lunch),
                                           (next_match_time, match_duration)]):
                next_match_time = self.lunch_end

            if i % nmatches_per_round == 0:
                round_no += 1
                # Add a break
                match_events.extend([{
                    "Time": next_match_time,
                    "EventName": "Break",
                    "RoundNo": 0,
                    "Room": f"Table {tableno}",
                    "Duration": self.config.table.match_break_duration,
                    "Team": -2
                } for tableno in range(1, 1 + self.config.tournament.ntables)])
                next_match_time = TimeUtils.add_times(
                    next_match_time,
                    self.config.table.match_break_duration
                )

        self.events = pd.concat([self.events, pd.DataFrame(match_events)], ignore_index=True)

    ## ASSIGN TEMPLATE TEAMS TO EVENTS ## 

    # Create judging assignments - no verification
    # randomized judging assignments. 
    def assign_judging_randomly(self, eventtype):
        self.clear_judging_events(eventtype)

        events = self.events[self.events["EventName"] == eventtype]
        events_sorted = events.sort_values(by=["Room", "Time"], ascending=True)
        teamnos = self.teamid_keys.copy()
        np.random.shuffle(teamnos).astype(int)
        events_sorted.loc[:, "Team"] = teamnos
        # Update self.events
        self.events.update(events_sorted)

    # Assign judging assignments - methodical
    def assign_judging_methodically(self):
        self.clear_judging_events("Project")
        self.clear_judging_events("Design")

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

    # Assign all judging events according to self.strategy_randomize
    def assign_all_judging(self, project_max_attempts=1e5, design_max_attempts=1e5):
        if self.strategy_randomize == "judging":
            for i in range(int(project_max_attempts)):
                if i % 1000 == 0:
                    print(f"STARTING (project) JUDGING ASSIGNMENT ATTEMPT {i}...")

                self.assign_judging_randomly("Project")
                good_proj = self.verify_schedule()
                if good_proj:
                    for j in range(int(design_max_attempts)):
                        if j % 1000 == 0:
                            print(f"  Trying design judging assignment attempt {j}...")
                        self.assign_judging_randomly("Design")
                        good_design = self.verify_schedule()
                        if good_design:
                            return True
            return False
        self.assign_judging_methodically()

    # Assign teams to matches - both random and methodical methods in this fn
    def assign_match_round(self, roundno):
        self.clear_table_events(roundno)

        table_events = self.events[self.events["RoundNo"] == roundno]
        table_events_sorted = table_events.sort_values(by=["Time", "Room"], ascending=True)

        teamnos = self.teamid_keys.copy()
        # np.random.shuffle(teamnos)

        if self.strategy_randomize == "matches":
            np.random.shuffle(teamnos)
        else: # methodical assignment of matches. 
            if roundno == 2:
                pass # keep as is
            elif roundno == 1:
                teamnos = [teamnos[-1]] + teamnos[:-1]  # shift by 1
            elif roundno == 3:
                new_teamnos = []
                for i in range(len(teamnos)//4):
                    a, b, c, d = teamnos[4*i :4*i+4]
                    new_teamnos.extend([a,c, b, d])
                new_teamnos.extend(teamnos[4*(len(teamnos)//4):]) # add remaining teams if not multiple of 4

                if len(teamnos) % 4 != 0: # more shuffling if required
                    a, b, c, d = new_teamnos[-4:]
                    new_teamnos[-4:] = [a, c, b, d]

                teamnos = new_teamnos

        assert len(teamnos) == len(table_events), "Team assignment length mismatch!"        

        table_events_sorted.loc[:, "Team"] = teamnos

        # Update self.events
        self.events.update(table_events_sorted)

    # Assign all match events according to self.strategy_randomize
    def assign_all_matches(self, max_startovers=1000, max_r1 = 1e5, max_r2 = 4e5, max_r3=16e5):

        if self.strategy_randomize == "judging":
            self.assign_match_round(1)
            self.assign_match_round(2)
            self.assign_match_round(3)
            return True
        
        # Randomize the matches. 
        
        for m in range(max_startovers):
            print(f"STARTING MATCH ASSIGNMENT ATTEMPT {m}..")
            # Try round 1
            for i in range(int(max_r1)):
                self.assign_match_round(1)
                if self.verbose and i%1000 == 0:
                    print(f"  Trying round 1 assignment attempt {i}...")
                if self.verify_schedule(check_opponents=False, check_table_diversity=False):
                    break

            if self.verify_schedule(check_opponents=False, check_table_diversity=False):
                if self.verbose:
                    print("FOUND ROUND 1 ASSIGNMENT AFTER ", i, "ATTEMPTS")
            else:
                continue

            # Try round 2
            for i in range(int(max_r2)):
                self.assign_match_round(2)
                if self.verbose and i%1000 == 0:
                    print(f"  Trying round 2 assignment attempt {i}...")
                if self.verify_schedule(check_opponents=True, check_table_diversity=False):
                    break

            if self.verify_schedule(check_opponents=True, check_table_diversity=False):
                if self.verbose:
                    print("FOUND ROUND 2 ASSIGNMENT AFTER ", i, "ATTEMPTS")
            else:
                continue

            # Try round 3
            for i in range(int(max_r3)):
                self.assign_match_round(3)
                if self.verbose and i%1000 == 0:
                    print(f"  Trying round 3 assignment attempt {i}...")
                if self.verify_schedule(check_opponents=True, check_table_diversity=True):
                    break
            
            if self.verbose:
                print("FOUND ROUND 3 ASSIGNMENT AFTER ", i, "ATTEMPTS")
                return True
        return False

    #################################################
    ################### UTILITIES ###################
    #################################################
    # remove all judging events from self.events and self.events_by_team
    def clear_judging_events(self, eventtype):
        # change the teamno of these columns to -1
        self.events.loc[self.events["EventName"] == eventtype, "Team"] = -1

    # Remove all table events from self.events and self.events_by_team
    # roundno = -1 means all rounds
    def clear_table_events(self, roundno=-1):
        if roundno == -1:
            self.events.loc[self.events["RoundNo"] != 0, "Team"] = -1
        else:
            self.events.loc[self.events["RoundNo"] == roundno, "Team"] = -1

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

    # check_opponents: check that teams have different opponents each round
    # check_table_diversity: check that teams see as many different tables as possible
    def verify_schedule(self, check_opponents = True, check_table_diversity = True):
        # Verify all teams have all events!!
        # Verify no overlaps for teams
        no_overlaps = self.verify_no_team_overlaps()
        if not no_overlaps:
            if self.veryverbose:
                print("Schedule verification failed: team overlaps found.")
            return False

        # Verify "gap" between events is >= whatever config says
        gap_ok, fail_team = self.verify_event_gap()
        if not gap_ok:
            if self.veryverbose:
                print(f"Schedule verification failed: team {fail_team} has insufficient gap between events.")
            return False
        else:
            if self.veryverbose:
                print(f"Smallest gap: {fail_team} minutes.")
        
        # Make sure all teams have different opponents for each table round
        if check_opponents:
            opps = self.verify_opponent_diversity()
            if not opps:
                if self.veryverbose:
                    print("Schedule verification failed: teams have repeated opponents.")
                return False
        
        # Make sure all teams see as many tables as possible.
        if check_table_diversity:
            for i in range(25):
                table_div = self.verify_table_diversity()
                if table_div == -1:
                    break
                if self.veryverbose:
                    print(f"Schedule verification: team {table_div} doesn't see enough tables. Attempting to fix...")

                self.fix_table_diversity(table_div)

            if table_div != -1:
                return False # We failed to fix the table diversity issue.


        # All checks passed!!
        return True 

    def verify_no_team_overlaps(self):
        for teamno in self.teamid_keys:
            # Create list of (start_time, duration) tuples
            time_blocks = self.get_team_events_interval_list(teamno)
            # Check for overlaps
            if TimeUtils.contains_overlap(time_blocks):
                if self.veryverbose:
                    print(f"Team {teamno} has overlapping events.")
                return False
        return True
    
    def verify_event_gap(self):
        min_gap = 100000
        for teamno in self.teamid_keys:
            time_blocks = self.get_team_events_interval_list(teamno)
            # Sort by start time
            time_blocks.sort(key=lambda x: x[0])
            for i in range(1, len(time_blocks)):
                prev_end = TimeUtils.add_times(time_blocks[i - 1][0], time_blocks[i - 1][1])
                curr_start = time_blocks[i][0]
                gap = TimeUtils.subtract_times(curr_start, prev_end)
                min_gap = min(min_gap, gap)
                if gap < self.config.team.time_between_events:
                    if self.veryverbose:
                        print(f"Team {teamno} has insufficient gap between events.")
                    return False, teamno
                
        return True, min_gap
    
    def verify_opponent_diversity(self):
        tablerounds = self.events[(self.events["RoundNo"] != 0) & (self.events["Team"] != -1)]
        match_groups = tablerounds.groupby(by=["Time"])
        match_tuples = (match_groups["Team"]).apply(lambda x: tuple(sorted(x)))
        if len(set(match_tuples)) != len(match_tuples):
            return False
        return True

    def see_unique_tables(self, teamno):
        tablerounds = self.events[(self.events["RoundNo"] != 0) & (self.events["Team"] != -1)]
        team_groups = tablerounds.groupby(by=["Team"])
        team_rounds = team_groups.get_group((teamno, ))
        tables_seen = team_rounds["Room"].unique()
        return len(tables_seen) == min(self.config.tournament.ntable_rounds, self.config.tournament.ntables)

    def verify_table_diversity(self):
        for team in self.teamid_keys:
            if not self.see_unique_tables(team):
                if self.veryverbose:
                    print(f"Team {team} has insufficient table diversity.")
                return team
        return -1
    
    def fix_table_diversity(self, teamno):
        # Find this team's table rounds and their opponents
        tablerounds = self.events[(self.events["RoundNo"] != 0) & (self.events["Team"] == teamno)]
        tabletimes = tablerounds["Time"].values
        teams_we_care_about = self.events[(self.events["RoundNo"] != 0) & \
                                (self.events["Time"].isin(tabletimes))]["Team"].unique().tolist()
        
        # swap round 1 opponent and see if it fixes the problem
        for round in range(1, 4):
            round_time = tablerounds[tablerounds["RoundNo"] == round]["Time"]
            round_match = self.events[(self.events["Time"] == round_time.values[0]) & \
                                       (self.events["RoundNo"] == round)]
            round_match.loc[:, "Team"] = round_match["Team"][::-1].values
            self.events.update(round_match)

            # check if the 4 teams we are messing with have been fixed
            fixed = True
            for team in teams_we_care_about:
                fixed &= self.see_unique_tables(team)

            # swap back if it didn't fix
            if not fixed:
                round_match.loc[:, "Team"] = round_match["Team"][::-1].values
                self.events.update(round_match)
            else:
                return 

    #####################################################
    ################### CSV UTILITIES ###################
    #####################################################
       
    # save the df to a csv
    def save_schedule_csv(self, filename):
        self.events.to_csv(filename, index=False)

    # get from csv
    def load_schedule_csv(self, filename):
        self.events = pd.read_csv(filename)

        # Turn all "Time" column into datetime.time objects
        self.events["Time"] = pd.to_datetime(self.events["Time"]).dt.time