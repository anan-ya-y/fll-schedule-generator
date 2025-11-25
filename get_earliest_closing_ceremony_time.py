# Returns the earliest possible closing ceremony time based on template and args
import argparse
import pandas as pd
from utils import TimeUtils

parser = argparse.ArgumentParser(description="Get earliest possible closing ceremony time based on template and args")
parser.add_argument("input_file", type=str, help="Template Schedule .csv file")
parser.add_argument("deliberation_length", type=int, help="Length of deliberation in minutes", default=60)
args = parser.parse_args()

# Read the input schedule
schedule_df = pd.read_csv(args.input_file)
# Change all Time entries into datetime.time objects - current entries are HH:MM:SS
schedule_df['Time'] = pd.to_datetime(schedule_df['Time'], format="%H:%M:%S").dt.time

# Get the latest event in each room
rooms = schedule_df['Room'].unique()
sorted_df = schedule_df.sort_values(["Time"], ascending=False).groupby(by=["Room"])

lastest_events = []
for room in rooms:
    room_events = sorted_df.get_group(room)
    lastest_event = room_events.iloc[0]
    lastest_events.append(lastest_event)

# Find the last judged event/match
latest_event = max(lastest_events, key=lambda x: x['Time'])
latest_event_end = TimeUtils.add_times(latest_event['Time'], int(latest_event['Duration']))

# Add deliberation time
earliest_closing_ceremony_time = TimeUtils.add_times(latest_event_end, int(args.deliberation_length))

print("Earliest possible closing ceremony time is:", earliest_closing_ceremony_time.strftime("%H:%M"))