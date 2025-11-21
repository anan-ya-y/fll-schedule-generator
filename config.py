from datetime import datetime as dt
import numpy as np
import pandas as pd
from utils import TimeUtils

class SubConfig:
    def __init__(self):
        pass

    def to_dict(self):
        ans = {}
        for item in self.__dict__.items():
            if type(item[1]) == type(dt.strptime("10:10", "%H:%M").time()):
                ans[item[0]] = item[1].strftime("%H:%M:%S")
            elif type(item[1]) == pd.DataFrame:
                ans[item[0]] = item[1].to_dict()
            else:
                ans[item[0]] = item[1]
        return ans

class Config:
    def __init__(self):
        self.seed = 2025

        # TOURNAMENT CONFIGURATION
        self.tournament = SubConfig()
        self.tournament.nteams = 20
        self.tournament.njudging_rooms = 2 # per type (total = 4 if this =2)
        self.tournament.ntables = 2
        self.tournament.ntable_rounds = 3
        self.tournament.design_room_names = ["D1", "D2"]
        self.tournament.project_room_names = ["P1", "P2"]
        
        # TABLE ROUNDS CONFIGURATION. 
        self.table = SubConfig()
        self.table.match_break_duration = 10
        self.table.nminutes_table_rnd1 = 10
        self.table.nminutes_table_allrounds = 8

        # JUDGING CONFIGURATION
        self.judging = SubConfig()
        self.judging.nminutes_judging = 10
        self.judging.nminutes_between_judging = 10
        self.judging.nteams_per_judging_sprint = 3

        # DAY CONFIGURATION
        self.day = SubConfig()
        self.day.lunch_start = "11:55"
        self.day.nminutes_lunch = 40
        self.day.start_time = "9:00"
        self.day.opening_ceremony_duration = 20
        self.day.matches_start_time = "9:35"
        self.day.judging_prep = 25 # # of minutes between end of opening ceremony & first judging
        self.day.closing_ceremony_time = "17:00"
        self.day.closing_ceremony_duration = 45

        # TEAM STUFF - this does NOT get saved to .JSON!!
        self.team = SubConfig()
        self.team.time_between_events = 10 # minutes; minimum time between end of 1 event and start of next. 
        self.team.teamlist_file = "teamlist.csv"

        # do not touch. 
        self.process()
        np.random.seed(self.seed)

    def process(self):
        self.tournament.nproject_rooms = self.tournament.njudging_rooms
        self.tournament.ndesign_rooms = self.tournament.njudging_rooms

        self.day.start_time = dt.strptime(self.day.start_time, "%H:%M").time()
        self.day.lunch_start = dt.strptime(self.day.lunch_start, "%H:%M").time()
        self.day.closing_ceremony_time = dt.strptime(self.day.closing_ceremony_time, "%H:%M").time()
        self.day.matches_start_time = dt.strptime(self.day.matches_start_time, "%H:%M").time()
        self.day.opening_ceremony_end_time = TimeUtils.add_times(self.day.start_time, self.day.opening_ceremony_duration)

        self.team.teamlist_file = "teamlist.csv"
        # read csv, turn it into df
        self.team.teamlist = pd.read_csv(self.team.teamlist_file)

        self.team.teamnames = self.team.teamlist["Team Name"].tolist()
        self.team.teamnos = self.team.teamlist["Team Number"].tolist()

        assert len(self.team.teamnames) == self.tournament.nteams, "Number of teams in teamlist does not match nteams in config."

        if len(self.team.teamnos) % 2 == 1:
            self.team.teamnames.append("XXX")
            self.team.teamnos.append(9999)  # dummy team number
            # add to self.team.teamlist
            self.team.teamlist = pd.concat([self.team.teamlist, pd.DataFrame([{"Team Name": "XXX", "Team Number": 9999, "Distance": 0}])], ignore_index=True)
            self.tournament.nteams += 1

        assert len(self.team.teamnames) == self.tournament.nteams, "Number of teams in teamlist does not match nteams in config."

        self.team.teamnos_to_names = {row["Team Number"]: row["Team Name"] for _, row in self.team.teamlist.iterrows()}
        self.team.teamnos_to_distances = {row["Team Number"]: row["Distance"] for _, row in self.team.teamlist.iterrows()}

        self.day.lunch_end = TimeUtils.add_times(self.day.lunch_start, self.day.nminutes_lunch)    

    def to_json(self, filename):
        import json
        completed_json_dict = {}

        for d in self.__dict__:
            if d != "team":  # do not save team stuff to JSON
                continue

            
            if type(self.__dict__[d]) == SubConfig:
                # need to convert to dict
                completed_json_dict[d] = self.__dict__[d].to_dict()
            else:
                # dump the value d
                completed_json_dict[d] = self.__dict__[d]
            
        with open(filename, 'w') as f:
            f.write(json.dumps(completed_json_dict, indent=4))

    def from_json(self, filename):
        import json
        with open(filename, 'r') as f:
            data = json.load(f)
            for key, value in data.items():
                setattr(self, key, value)