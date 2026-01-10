"""Simple demo: push a Survey to the remote server."""

from edsl import Survey

# First push - just one line!
s = Survey.example()
s.git_push(alias="my-survey-new", description="Example survey", username="john")
# Creates "origin" remote from config, sets _info, commits, creates repo, pushes

print("Pushed successfully!")
print("View at: http://localhost:8765/john/my-survey-new")

# Clone it back
cloned = Survey.git_clone("my-survey-new", username="john")
print(f"Cloned survey has {len(cloned.questions)} questions")
