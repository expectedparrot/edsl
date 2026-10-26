# EDSL examples

Use these Python examples to build a study or analyze responses:

- [First survey](quickstart.py): construct a survey and inspect a local test response.
- [Agents](agents.py) and [scenarios](scenarios.py): vary profiles and study inputs.
- [Survey logic](survey_logic.py): add stopping rules, piping, and memory.
- [Results](results.py) and [datasets](dataset.py): select, filter, and export data.
- [Local caching](caching.py): reuse responses and save a cache.
- [Importing data](importing_data.py) and [files](files.py): prepare tabular inputs and attachments.

Copy an example into a notebook to inspect its objects interactively, or run it
as a Python script. In a notebook, a final expression displays its value;
assigning it to a variable does not. Use `.print()` to display an EDSL table in
a script. Comments show optional conversions to Python lists and pandas.

The examples use small synthetic inputs. `quickstart.py` and `caching.py` use a
local test model; `results.py` contains fabricated answers. These demonstrate
EDSL operations rather than research findings. Other examples construct studies
or transform local data without generating model responses. Some examples write
CSV, cache, or other local files; EDSL runs may also save local execution artifacts.

For real model responses, configure model access and review costs before running.
Follow the [first-survey tutorial](../en/latest/starter_tutorial.mdx) for the full workflow.
