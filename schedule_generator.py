from config import Config
import schedule_latex as sln
from schedule import Tournament

c = Config()
t = Tournament(c)#, csvfile="tournament_schedule.csv")
sln.create_team_schedule(t)
sln.create_judging_schedule(t)
sln.create_ref_schedule(t)
sln.create_fllt(t, "12/7/25")
