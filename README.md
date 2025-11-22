# fll-schedule-generator

## 1. GENERATE YOUR TEMPLATE. 
Either find an `old tournament_schedule.csv` file, or create one. To create one, fill out config.py with your desired configurations, and run the code. Hopefully you find a tournament. 

## 2. APPLY TO YOUR TOURNAMENT. 
Create tournament_details.json with the following information:

```
{
    "teamlist": "teamlist.csv", 
    "design_rooms": [
        rooms
    ], 
    "project_rooms": [
        rooms
    ]
}
```

`teamlist.csv` should be formatted like so:

```
Team #,Team Name,Distance
46, Amazing team 46, 46 
23, Amazing team 23, 23 
...
```
You will need to adjust schedule_generator.py for the right Tournament() items in the constructor

## 3. GENERATE YOUR PDFS AND FLLT SCHEDULE. 

In schedule_generator.py:
```
sln.create_team_schedule(t)
sln.create_judging_schedule(t)
sln.create_ref_schedule(t)
sln.create_fllt(t, "MM/D/YY")
```
