from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from utils import TimeUtils

class SubConfig:
    def __init__(self):
        pass

class Config:
    def __init__(self):
        self.seed = 2025

        # TOURNAMENT CONFIGURATION
        self.tournament = SubConfig()
        self.tournament.nteams = 20
        self.tournament.njudging_rooms = 2 # per type (total = 4 if this =2)
        self.tournament.ntables = 2
        self.tournament.ntable_rounds = 3
        self.tournament.design_room_names = ["a", "c"]
        self.tournament.project_room_names = ["b", "d"]
        
        # TABLE ROUNDS CONFIGURATION. 
        self.table = SubConfig()
        self.table.match_break_duration = 10
        self.table.nminutes_table_rnd1 = 8
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

        # TEAM STUFF
        self.team = SubConfig()
        self.team.time_between_events = 10 # minutes; minimum time between end of 1 event and start of next. 
        self.team.teamlist_file = "teamlist.csv"

        # do not touch. 
        self.process()
        np.random.seed(self.seed)

    def process(self):
        self.tournament.nproject_rooms = self.tournament.njudging_rooms
        self.tournament.ndesign_rooms = self.tournament.njudging_rooms


        self.day.start_time = datetime.strptime(self.day.start_time, "%H:%M").time()
        self.day.lunch_start = datetime.strptime(self.day.lunch_start, "%H:%M").time()
        self.day.closing_ceremony_time = datetime.strptime(self.day.closing_ceremony_time, "%H:%M").time()
        self.day.matches_start_time = datetime.strptime(self.day.matches_start_time, "%H:%M").time()
        self.day.opening_ceremony_end_time = TimeUtils.add_times(self.day.start_time, self.day.opening_ceremony_duration)

        self.team.teamlist_file = "teamlist.csv"
        # read csv, turn it into df
        self.team.teamlist = pd.read_csv(self.team.teamlist_file)

        self.team.teamnames = self.team.teamlist["Team Name"].tolist()
        self.team.teamnos = self.team.teamlist["Team Number"].tolist()
        self.team.teamnos_to_names = {row["Team Number"]: row["Team Name"] for _, row in self.team.teamlist.iterrows()}
        self.team.teamnos_to_distances = {row["Team Number"]: row["Distance"] for _, row in self.team.teamlist.iterrows()}

        assert len(self.team.teamnames) == self.tournament.nteams, "Number of teams in teamlist does not match nteams in config."

        self.day.lunch_end = TimeUtils.add_times(self.day.lunch_start, self.day.nminutes_lunch)    
