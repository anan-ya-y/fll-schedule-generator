from utils import TimeUtils, Event
import numpy as np

class Tournament:
    def __init__(self, config):
        self.config = config
        self.events = [] # All events in the tournament
        self.events_by_team = {} # {teamno : [Events]}

        # Strategy: Create a template of events. 
        # Then, assign teams by distance. 
        
        # Strategy for template:
        # 1. Fix the Judging rounds
        # 2. Match Table Round 1. 
        # 3. Match Table Round 3. 
        # 4. Match Table Round 2 - Try n times, then start over. 

        