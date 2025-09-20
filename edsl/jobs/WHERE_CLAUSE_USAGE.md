# Where Clause Filtering in EDSL Jobs

## Overview

The `where()` method in EDSL Jobs now supports filtering interviews based on conditions that compare agent, scenario, and model attributes. This uses the `simpleeval` library to safely evaluate expressions.

## Installation

Make sure you have `simpleeval` installed:

```bash
pip install simpleeval
```

## Usage

### Basic Syntax

Use the `where()` method to add filtering conditions to your jobs:

```python
from edsl.jobs import Jobs
from edsl.agents import Agent  
from edsl.scenarios import Scenario

# Create agents with different ages
agent1 = Agent(traits={"age": 25, "status": "employed"})
agent2 = Agent(traits={"age": 30, "status": "employed"})
agent3 = Agent(traits={"age": 25, "status": "unemployed"})

# Create scenarios with different ages
scenario1 = Scenario({"age": 25, "location": "office"})
scenario2 = Scenario({"age": 30, "location": "home"})

# Create a job and filter where agent age matches scenario age
job = Jobs(survey).by(agent1, agent2, agent3).by(scenario1, scenario2)
filtered_job = job.where("agent.age == scenario.age")

# This will only create interviews where the agent's age matches the scenario's age
interviews = filtered_job.interviews()
```

### Supported Expressions

The where clauses support standard Python comparison and logical operators:

#### Equality and Comparison
```python
job.where("agent.age == scenario.age")
job.where("agent.status == 'employed'") 
job.where("model.temperature >= 0.5")
job.where("scenario.priority > 5")
```

#### Logical Operators
```python
job.where("agent.age >= 25 and agent.status == 'employed'")
job.where("scenario.location == 'office' or scenario.location == 'home'")
job.where("not (agent.age < 18)")
```

#### Multiple Where Clauses
You can chain multiple where clauses - all must be true:

```python
job.where("agent.age >= 18").where("scenario.priority > 3").where("model.temperature < 1.0")
```

## Available Attributes

### Agent Attributes
- Access agent traits: `agent.age`, `agent.status`, etc.
- Any attribute in the agent's `traits` dictionary

### Scenario Attributes  
- Access scenario data: `scenario.location`, `scenario.priority`, etc.
- Any attribute in the scenario's `data` dictionary

### Model Attributes
- Access model parameters: `model.temperature`, `model.model_name`, etc.
- Any non-private attribute of the model object

## Examples

### Filter by Demographics
```python
# Only interviews where agent is adult and scenario is workplace
job.where("agent.age >= 18 and scenario.location == 'office'")
```

### Filter by Model Settings
```python
# Only use high-temperature models for creative scenarios
job.where("model.temperature > 0.7 and scenario.type == 'creative'")
```

### Complex Conditions
```python
# Multiple criteria
job.where("(agent.experience == 'senior' and scenario.difficulty == 'hard') or (agent.experience == 'junior' and scenario.difficulty == 'easy')")
```

## Error Handling

If a where clause evaluation fails (e.g., accessing non-existent attributes), the interview combination is skipped and a warning is printed:

```
Warning: Where clause 'agent.nonexistent == 5' evaluation failed: 'nonexistent' not found
```

## Performance Notes

- Where clause filtering happens during interview generation, so it's efficient
- Complex expressions may impact performance for large combinations
- Consider the order of where clauses - put more selective conditions first

## Implementation Details

The filtering uses the `simpleeval` library which provides:
- Safe evaluation (no access to dangerous functions)
- Support for standard Python operators
- Restricted function set for security

Attributes are made available through an `AttributeDict` class that allows dot-notation access to dictionary keys.
