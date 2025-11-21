from utils import TimeUtils, Event
import numpy as np

class Tournament:
    def __init__(self, config):
        self.config = config
        self.events = [] # All events in the tournament
        self.events_by_team = {} # {teamno : [Events]}
        self.nteams = self.config.tournament.nteams

        self.lunch_start = self.config.day.lunch_start
        self.lunch_end = self.config.day.lunch_end

        # Strategy: Create a template of events. 
        # Then, assign teams by distance. 
        
        # Strategy for template:
        # 1. Fix the Judging rounds
        self.judging_times = self.get_judging_times()
        self.assign_judging(self.judging_times)
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
        return judging_times

    # Create judging assignments - update self.events and self.events_by_team
    def assign_judging(self, judging_times, shuffle_teams=False):
        self.clear_judging_events()

        team_order = np.arange(1, 1 + self.nteams)
        if shuffle_teams:
            np.random.shuffle(team_order)

        # Assign the project rooms in order. 
        team_idx = 0
        for roomno in range(self.config.tournament.nproject_rooms):
            for time in judging_times:
                if team_idx >= self.nteams:
                    break
                teamno = team_order[team_idx]
                event = Event(
                    time=time,
                    title="Project",
                    room=f"Project Room {roomno + 1}",
                    duration=self.config.judging.nminutes_judging,
                    eventtype="project",
                    team=teamno
                )
                self.events.append(event)
                team_idx += 1

        # Assign the design rooms in half order
        team_idx = 0
        design_judging_times = judging_times[len(judging_times)//2:] + \
                                judging_times[:len(judging_times)//2]
        for roomno in range(self.config.tournament.ndesign_rooms):
            for time in design_judging_times:
                if team_idx >= self.nteams:
                    break
                teamno = team_order[team_idx]
                event = Event(
                    time=time,
                    title="Design",
                    room=f"Design Room {roomno + 1}",
                    duration=self.config.judging.nminutes_judging,
                    eventtype="design",
                    team=teamno
                )
                self.events.append(event)
                team_idx += 1

        self.update_events_by_team()

    #################################################
    ################### UTILITIES ###################
    #################################################
    # remove all judging events from self.events and self.events_by_team
    def clear_judging_events(self):
        new_events = []
        for event in self.events:
            if event.title.lower() in ["project", "design"]:
                continue
            new_events.append(event)
        self.events = new_events

        self.update_events_by_team()

    # Remove all table events from self.events and self.events_by_team
    # roundno = -1 means all rounds
    def clear_table_events(self, roundno=-1):
        new_events = []
        for event in self.events:
            if event.title.lower().startswith("round"):
                if roundno == -1 or event.title.lower() == f"round {roundno}":
                    continue
            new_events.append(event)
        self.events = new_events

        self.update_events_by_team()

    # Update self.events_by_team based on self.events
    # TODO MAKE SMARTER. 
    def update_events_by_team(self):
        self.events_by_team = {}
        for event in self.events:
            if event.team == -1:
                continue
            if event.team not in self.events_by_team:
                self.events_by_team[event.team] = []
            self.events_by_team[event.team].append(event)


    
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
        for teamno, events in self.events_by_team.items():
            # Create list of (start_time, duration) tuples
            time_blocks = [(event.time, event.duration) for event in events]
            if TimeUtils.contains_overlap(time_blocks):
                print(f"Team {teamno} has overlapping events.")
                return False
        return True
    
    def verify_event_gap(self):
        for teamno, events in self.events_by_team.items():
            time_blocks = [(event.time, event.duration) for event in events]
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