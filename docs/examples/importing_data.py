import csv
from pathlib import Path
from edsl import AgentList, ScenarioList

def write_fixture(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

write_fixture("messages.csv", [
    {"record_id": "m1", "message": "Your report is ready to download."},
    {"record_id": "m2", "message": "Download your report with the Export button."},
])
write_fixture("profiles.csv", [
    {"profile_id": "p1", "experience": "new user"},
    {"profile_id": "p2", "experience": "frequent user"},
])

records = ScenarioList.from_source("csv", "messages.csv")
agents = AgentList.from_source("csv", "profiles.csv", name_field="profile_id")
assert len(records) == 2
assert len(agents) == 2
