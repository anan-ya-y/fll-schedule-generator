from config import Config
import schedule_latex as sln
from schedule import Tournament

c = Config()
# c.to_json("config.json")

# c = Config.from_json("config.json")

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

t = Tournament(c)#, csvfile="tournament_schedule.csv")
sln.create_team_schedule(t)
sln.create_judging_schedule(t)
sln.create_ref_schedule(t)
t.save_schedule_csv("tournament_schedule.csv")
