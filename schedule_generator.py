from config import Config
from schedule import Schedule
import schedule_latex as sl

c = Config()

# create the slots to be filled. 
s = Schedule(c)

judge_times = s.get_judging_times()
match_times = s.get_match_times()

all_times = judge_times + match_times
all_times.sort()


# for i in all_times:
#     print(f"{i}: {"J" if i in judge_times else " "} {"M" if i in match_times else " "}")

s.set_judge_teams(judge_times, ["P1", "P2"], ["D1", "D2"])

s.set_matches(match_times)

s.set_events_by_team()

sl.create_team_schedule(s)