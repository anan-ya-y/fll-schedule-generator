from datetime import datetime 
import datetime

class TimeUtils:
    @staticmethod
    def add_times(time, td):
        if type(td) is int:
            td = datetime.timedelta(minutes=td)
            full_datetime = datetime.datetime.combine(datetime.datetime.today(), time) + td
            return full_datetime.time()
        if type(td) is datetime.time:
            full_datetime = datetime.datetime.combine(datetime.datetime.today(), time) + \
                datetime.timedelta(hours=td.hour, minutes=td.minute, seconds=td.second)
            return full_datetime.time()
        raise ValueError("td must be int or datetime.time")

    @staticmethod
    def subtract_times(time, td):
        if type(td) is int:
            td = datetime.timedelta(minutes=td)
            full_datetime = datetime.datetime.combine(datetime.datetime.today(), time) - td
            return full_datetime.time()
        if type(td) is datetime.time:
            diff_td = datetime.datetime.combine(datetime.datetime.today(), time) - \
                datetime.timedelta(hours=td.hour, minutes=td.minute, seconds=td.second)
            diff_td = diff_td.time()
            difference_minutes = diff_td.hour * 60 + diff_td.minute
            return difference_minutes
        raise ValueError("td must be int or datetime.time")
    
    # Intervals is a list [(starttime, duration), ...]
    # Returns True if any overlap. False otherise. 
    @staticmethod
    def contains_overlap(intervals):
        times_list = [(k[0], TimeUtils.add_times(k[0], k[1])) 
                      for k in intervals]
        times_list.sort(key=lambda x: x[0])  # sort by start time
        for i in range(1, len(times_list)):
            prev_end = times_list[i - 1][1]
            curr_start = times_list[i][0]
            if curr_start < prev_end:
                return True
        return False
    
class Event:
    def __init__(self, time, title, room, duration, eventtype=None, team=-1):
        self.time = time
        self.title = title # "Project", "Design", "Round 1", "Round 2", "Round 3", or "Opening/Closing/etc"
        self.room = room
        self.duration = duration
        self.team = team
        
    def __str__(self):
        team_str = f" for Team {self.team}" if self.team != -1 else ""
        return f"{self.time} - {self.title} in {self.room} for {self.duration} minutes{team_str}"


