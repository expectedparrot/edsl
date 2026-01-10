"""Simple demo: push a Survey to the remote server."""

from edsl import Survey
from edsl.versioning import ObjectVersionsServer

server = ObjectVersionsServer("http://localhost:8765")

s = Survey.example()

result = server.create(alias="new_survey-two", description="Example survey")
s.git_add_remote("origin", result["remote"])
s.git_push()

print("Pushed successfully!")
print(f"Repo ID: {result['repo_id']}")
print("View at: http://localhost:8765/")


news = Survey.git_clone(result['remote'], "main")