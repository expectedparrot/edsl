import pandas as pd
from edsl import Dataset

frame = pd.DataFrame({
    "condition": ["short", "explicit", "short", "explicit"],
    "score": [3, 5, 2, 4],
})
dataset = Dataset.from_pandas_dataframe(frame)
selected = dataset.filter("score >= 4").order_by("score", reverse=True)
with_flag = dataset.mutate("high_score = score >= 4")
# Display in a notebook: put selected on the last line of a cell.
# Display in a script: selected.print()
# Convert to pandas when you need DataFrame operations.
analysis_frame = selected.to_pandas()
selected.to_csv("selected_scores.csv")
