import pandas as pd
import argparse
from utils import TimeUtils

parser = argparse.ArgumentParser(description="Change lunch length, given a template file")
parser.add_argument("input_file", type=str, help="Template Schedule .csv file")
parser.add_argument("output_file", type=str, help="Output Schedule .csv file", default="modified_schedule.csv")
parser.add_argument("lunch_length", type=int, help="New lunch length in minutes", default=60)
args = parser.parse_args()

# Read the input schedule
schedule_df = pd.read_csv(args.input_file)
# Change all Time entries into datetime.time objects - current entries are HH:MM:SS
schedule_df['Time'] = pd.to_datetime(schedule_df['Time'], format="%H:%M:%S").dt.time

# Find all lunch events
lunch_df = schedule_df[schedule_df['EventName'] == 'Lunch']
old_lunch_length = lunch_df['Duration'].iloc[0]
old_lunch_start = lunch_df['Time'].iloc[0]
lunch_df.loc[:, 'Duration'] = args.lunch_length

time_diff = int(args.lunch_length - old_lunch_length)

after_lunch_events = schedule_df[schedule_df['Time'] > old_lunch_start]
after_lunch_events.loc[:, 'Time'] = after_lunch_events['Time'].apply(lambda t: TimeUtils.add_times(t, time_diff))

# Update the original schedule with modified lunch and subsequent events
schedule_df.update(lunch_df)
schedule_df.update(after_lunch_events)
# Save the modified schedule
schedule_df.to_csv(args.output_file, index=False)
