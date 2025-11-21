from config import Config
from schedule import Schedule
import schedule_latex as sl
import schedule_latex_new as sln
from schedule_new import Tournament

c = Config()

# create the slots to be filled. 
# s = Schedule(c)

# judge_times = s.get_judging_times()
# match_times = s.get_match_times()

# all_times = judge_times + match_times
# all_times.sort()

# s.set_judge_teams(judge_times, ["P1", "P2"], ["D1", "D2"])

# s.set_matches(match_times)
# i = 0
# while not s.validate_schedule():
#     if i % 100 == 0:
#         print("Schedule invalid, regenerating matches...")
#     i += 1
#     s.set_matches(match_times)

# s.set_events_by_team()

# sl.create_team_schedule(s)

t = Tournament(c)
sln.create_team_schedule(t)
