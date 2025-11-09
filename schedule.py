from datetime import datetime as dt
import datetime
import numpy as np

class TimeUtils:
    @staticmethod
    def add_times(time, td):
        if type(td) is int:
            td = datetime.timedelta(minutes=td)
            full_datetime = datetime.datetime.combine(datetime.datetime.today(), time) + td
            return full_datetime.time()
        if type(td) is datetime.time:
            full_datetime = datetime.datetime.combine(datetime.datetime.today(), time) + datetime.timedelta(hours=td.hour, minutes=td.minute, seconds=td.second)
            return full_datetime.time()
        raise ValueError("td must be int or datetime.time")

    @staticmethod
    def subtract_times(time, td):
        if type(td) is int:
            td = datetime.timedelta(minutes=td)
            full_datetime = datetime.datetime.combine(datetime.datetime.today(), time) - td
            return full_datetime.time()
        if type(td) is datetime.time:
            full_datetime = datetime.datetime.combine(datetime.datetime.today(), time) - datetime.timedelta(hours=td.hour, minutes=td.minute, seconds=td.second)
            return full_datetime.time()
        raise ValueError("td must be int or datetime.time")
    
    @staticmethod
    def is_during_lunch(lunch_start, lunch_duration, time):
        # if time is before lunch_start
        if datetime.datetime.combine(datetime.datetime.today(), time) < datetime.datetime.combine(datetime.datetime.today(), lunch_start):
            return False

        difference = TimeUtils.subtract_times(time, lunch_start)
        difference = difference.hour * 60 + difference.minute
        return difference < lunch_duration

class Event:
    def __init__(self, time, title, room, duration, team=-1):
        self.time = time
        self.title = title
        self.room = room
        self.duration = duration
        self.team = team
        
    def __str__(self):
        team_str = f" for Team {self.team}" if self.team != -1 else ""
        return f"{self.time} - {self.title} in {self.room} for {self.duration} minutes{team_str}"

class Schedule:
    def __init__(self, config):
        self.config = config
        self.events = []
        self.events_by_team = {} # team : {round 1: (time, roomno), ...}

        self.judging_times = self.get_judging_times()

        self.create_opening_ceremonies()
        self.create_closing_ceremonies()

    def create_opening_ceremonies(self):
        self.events.append(
            Event(time=self.config.day_start_time,
                  title="Opening Ceremonies",
                  room="OPENING CEREMONIES ROOM",
                  duration=self.config.opening_ceremony_duration,
                  team=-1)
        )

    def create_closing_ceremonies(self):
        self.events.append(
            Event(time=self.config.closing_ceremony_time,
                  title="Closing Ceremonies",
                  room="CLOSING CEREMONIES ROOM",
                  duration=self.config.closing_ceremony_duration,
                  team=-1)
        )

    def create_lunch(self):
        self.events.append(
            Event(time=self.config.lunch_start,
                  title="Lunch",
                  room="LUNCH ROOM",
                  duration=self.config.nminutes_lunch,
                  team=-1)
        )

    def __str__(self):
        s = ""
        for event in self.events:
            s += f"{event.time} - {event.title} in {event.room} for {event.duration} minutes\n"

        return s

    def get_judging_times(self):
        judging_start_time = TimeUtils.add_times(self.config.day_start_time, self.config.opening_ceremony_duration + self.config.day_prep_time)

        # number of judging slots required:
        njudging_slots = (self.config.nteams * 2) / (self.config.nproject_rooms + self.config.ndesign_rooms)
        njudging_slots = int(np.ceil(njudging_slots))

        next_judging_time = judging_start_time
        judging_times = []
        for i in range(1, 1+njudging_slots):
            judge_start_time = next_judging_time
            judging_times.append(judge_start_time)

            next_judging_time = TimeUtils.add_times(next_judging_time, self.config.nminutes_judging + self.config.nminutes_between_judging)

            if i % self.config.nteams_per_judging_sprint == 0:
                next_judging_time = TimeUtils.add_times(next_judging_time, 15)

            # make sure no judging runs through lunch
            lunch_end_time = TimeUtils.add_times(self.config.lunch_start, self.config.nminutes_lunch)
            if TimeUtils.is_during_lunch(self.config.lunch_start, self.config.nminutes_lunch, judge_start_time) or \
                TimeUtils.is_during_lunch(self.config.lunch_start, self.config.nminutes_lunch, next_judging_time):
                next_judging_time = lunch_end_time

        return judging_times
    
    # (round 1 times, round 2 times, ..)
    # ASSUMES 1 SET OF TABLES... 
    def get_match_times(self):
        nrounds = self.config.ntable_rounds

        nmatches_per_round = self.config.nteams // self.config.ntables

        round_times = []

        round_num = 1
        next_match_time = self.config.matches_start_time
        for i in range(1, 1+nmatches_per_round * nrounds):
            if round_num == 1:
                duration = self.config.nminutes_table_rnd1
            else:
                duration = self.config.nminutes_table_allrounds

            match_start_time = next_match_time
            round_times.append(match_start_time)

            next_match_time = TimeUtils.add_times(match_start_time, duration)

            # make sure no matches run through lunch
            lunch_end_time = TimeUtils.add_times(self.config.lunch_start, self.config.nminutes_lunch)
            if TimeUtils.is_during_lunch(self.config.lunch_start, self.config.nminutes_lunch, match_start_time) or \
                TimeUtils.is_during_lunch(self.config.lunch_start, self.config.nminutes_lunch, next_match_time):
                next_match_time = lunch_end_time

            if i % nmatches_per_round == 0:
                round_num += 1
                # add break
                next_match_time = TimeUtils.add_times(next_match_time, self.config.match_break_duration)
                               
        return round_times

    def set_judge_teams(self, judge_times, project_rooms, design_rooms):
        team_ids = np.array(list(range(1, self.config.nteams + 1)))

        robot_design_judge_order = np.reshape(team_ids, (self.config.ndesign_rooms, -1))
        half_teams = robot_design_judge_order.shape[1] // 2
        project_judge_order = np.hstack((robot_design_judge_order[:, half_teams:], 
                                    robot_design_judge_order[:, :half_teams]))
        njudging_slots = robot_design_judge_order.shape[1]
        
        # Add project judging rooms 
        judge_times_all = judge_times * self.config.nproject_rooms
        project_rooms_all = np.array([[p] * njudging_slots for p in project_rooms]).flatten()
        for t, teamid, room in zip(judge_times_all, project_judge_order.flatten(), project_rooms_all):
            self.events.append(
                Event(time=t,
                      title="Project Judging",
                      room=room,
                      duration=self.config.nminutes_judging,
                      team=teamid)
            )
            # print(f"Assigned Project Judging: Team {teamid} at {t} in {room}")

        # add design judging rooms
        judge_times_all = judge_times * self.config.ndesign_rooms
        design_rooms_all = np.array([[d] * njudging_slots for d in design_rooms]).flatten()
        for t, teamid, room in zip(judge_times_all, robot_design_judge_order.flatten(), design_rooms_all):
            self.events.append(
                Event(time=t,
                      title="Robot Design Judging",
                      room=room,
                      duration=self.config.nminutes_judging,
                      team=teamid)
            )
            # print(f"Assigned Robot Design Judging: Team {teamid} at {t} in {room}")

        return robot_design_judge_order, project_judge_order
    
    def set_matches(self, match_times):
        team_ids = np.array(list(range(1, self.config.nteams + 1)))
        rounds = []

        match_times_round = np.array(match_times).reshape((self.config.ntable_rounds, -1))

        for round in range(self.config.ntable_rounds):
            round_contents = np.random.permutation(team_ids)
            rounds.append(round_contents)

        # Add matches to self.events. 
        for round_num in range(self.config.ntable_rounds):
            match_times_all = [[k] * self.config.ntables for k in match_times_round[round_num]]
            match_times_all = np.array(match_times_all).flatten()
            team_ids_all = rounds[round_num]
            tables_all = list(range(1, self.config.ntables+1)) * (len(team_ids_all) // self.config.ntables)

            for t, teamid, table in zip(match_times_all, team_ids_all, tables_all):
                self.events.append(
                    Event(time=t,
                          title=f"Table Round {round_num + 1}",
                          room=f"Table {table}",
                          duration=(self.config.nminutes_table_rnd1 if round_num == 0 else self.config.nminutes_table_allrounds),
                          team=teamid)
                )
                # print(f"Assigned Table Round {round_num + 1}: Team {teamid} at {t} on Table {table}")
        
    def set_events_by_team(self):
        for event in self.events:
            # time, title, room, duration, team
            if event.team == -1:
                continue
            if event.team not in self.events_by_team:
                self.events_by_team[event.team] = {}
            if "Table" in event.title:
                round_no = int(event.title.split()[-1])
                self.events_by_team[event.team][f"Round {round_no}"] = (event.time, event.room, event.duration)
            elif "Judging" in event.title:
                if "Project" in event.title:
                    self.events_by_team[event.team]["P"] = (event.time, event.room, event.duration)
                elif "Robot Design" in event.title:
                    self.events_by_team[event.team]["RD"] = (event.time, event.room, event.duration)
        return self.events_by_team
    
    def get_table_events(self):
        table_events = {} # time: (Team1, team2)
        for event in self.events:
            if "Table" in event.title:
                if event.time not in table_events:
                    table_events[event.time] = []
                table_events[event.time].append(event.team)
        return table_events

    # in: list of events [(time, duration), ...]
    # out True if any overlap. False otherwise
    def times_overlap(self, events):
        times_list = [(k[0], TimeUtils.add_times(k[0], k[1])) for k in events]
        times_list.sort(key = lambda x: x[0]) # sort by start time
        for i in range(1, len(times_list)):
            prev_end = times_list[i-1][1]
            curr_start = times_list[i][0]
            if curr_start < prev_end:
                return True
        return False

    def validate_schedule(self):
        self.set_events_by_team()
        # Make sure teams have no overlapping events. 
        for teamno, teamevents in self.events_by_team.items():
            times = [(k[0], k[2]) for k in teamevents.values()] # (time, duration)
            if self.times_overlap(times):
                return False

        print("no overlaps!!")
        # make sure all teams see as many tables as possible
        # ASSUMES 2 TABLES ONLY FOR NOW. 
        for teamevents in self.events_by_team.values():
            r1_table = teamevents["Round 1"][1]
            r2_table = teamevents["Round 2"][1]
            r3_table = teamevents["Round 3"][1]
            if len(set([r1_table, r2_table, r3_table])) < min(self.config.ntables, 3):
                return False

        # make sure all teams have different opponents for each round
        table_events = self.get_table_events()
        team_opponents = {} # teamno: [opponents]
        for time, teamnos in table_events.items():
            a, b = teamnos[0], teamnos[1]
            if a not in team_opponents:
                team_opponents[a] = []
            if b not in team_opponents:
                team_opponents[b] = []
            team_opponents[a].append(b)
            team_opponents[b].append(a)

        for team, opponents in team_opponents.items():
            if len(opponents) != len(set(opponents)):
                return False

        return True
