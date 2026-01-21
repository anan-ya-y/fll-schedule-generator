from config import Config
import schedule_latex as sln
from schedule import Tournament
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument('--config', type=str, help="Path to config JSON file")
parser.add_argument('--tournament_details', type=str, help="Path to tournament details JSON file", required=True)
parser.add_argument('--output_folder', type=str, help="Output folder for generated schedules", default="output/")
parser.add_argument("--template_csv", type=str, help="Path to template CSV file for tournament")
parser.add_argument("--tournament_date", type=str, help="Date of the tournament (for FLLT); M/D/YY", required=True)
args = parser.parse_args()

c = Config()
c.to_json("config_generated.json")
if args.config:
    c.from_json(args.config) 

os.makedirs(args.output_folder, exist_ok=True)

t = Tournament(args.output_folder, \
                config=c, \
                csvfile=args.template_csv if args.template_csv else None, \
                veryverbose=True, \
                tournament_details_json=args.tournament_details
                ) #csvfile="tournament_schedule.csv")

sln.create_fllt(t, args.output_folder, args.tournament_date )
sln.create_team_schedule(t, args.output_folder)
sln.create_judging_schedule(t, args.output_folder)
sln.create_ref_schedule(t, args.output_folder)
sln.create_room_schedule(t, args.output_folder)

print()
print("YOU SHOULD SEE 5 OUTPUT FILES:")
print(" - fllt_schedule.csv")
print(" - judging_schedule.pdf")
print(" - ref_schedule.pdf")
print(" - team_schedule.pdf")
print(" - room_schedule.pdf")
