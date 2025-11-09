from utils import TimeUtils, Event
import numpy as np

class Tournament:
    def __init__(self, config):
        self.config = config
        self.events = [] # All events in the tournament
        self.events_by_team = {} # {teamno : [Events]}

        self.lunch_start = self.config.day.lunch_start

        # Strategy: Create a template of events. 
        # Then, assign teams by distance. 
        
        # Strategy for template:
        # 1. Fix the Judging rounds
        # 2. Match Table Round 1. 
        # 3. Match Table Round 3. 
        # 4. Match Table Round 2 - Try n times, then start over. 

    # Returns the judging slots. 
    def get_judging_times(self):
        judging_start_time = TimeUtils.add_times( 
            self.config.day.opening_ceremony_end_time,
            self.config.day.judging_prep 
        )
        
        # Number of judging slots required. 
        total_judging_rooms = self.config.tournament.nproject_rooms + \
                                self.config.tournament.ndesign_rooms
        n_judging_slots = (self.config.tournament.nteams * 2) / total_judging_rooms

        judging_times = []
        next_judging_time = judging_start_time
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
            # if TimeUtils.contains_overlap([(self.lunch_start, self.lunch_end)]):
