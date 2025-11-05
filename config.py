from datetime import datetime, timedelta

class Config:
    def __init__(self):
        self.nproject_rooms = 2
        self.ndesign_rooms = 2
        self.ntables = 2
        self.ntable_rounds = 3
        self.match_break_duration = 10

        self.nteams = 20

        self.nminutes_judging = 10
        self.nminutes_between_judging = 10
        self.nteams_per_judging_sprint = 3

        self.lunch_start = "12:00"
        self.nminutes_lunch = 45

        self.nminutes_table_rnd1 = 10
        self.nminutes_table_allrounds = 8

        self.day_start_time = "9:00"
        self.opening_ceremony_duration = 20
        self.matches_start_time = "9:35"
        self.day_prep_time = 25 # # of minutes between end of opening ceremony & first competition

        self.closing_ceremony_time = "17:00"
        self.closing_ceremony_duration = 45

        self.process()

    def process(self):
        self.day_start_time = datetime.strptime(self.day_start_time, "%H:%M").time()
        self.lunch_start = datetime.strptime(self.lunch_start, "%H:%M").time()
        self.closing_ceremony_time = datetime.strptime(self.closing_ceremony_time, "%H:%M").time()
        self.matches_start_time = datetime.strptime(self.matches_start_time, "%H:%M").time()


