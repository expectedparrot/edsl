# EDSL Service Framework

Create web services from EDSL code without knowing FastAPI or web development.

## Quick Example

```python
from edsl import QuestionFreeText, Agent, AgentList
from edsl.extensions import edsl_service, input_param, output_schema

@edsl_service(
    name="Simple Survey",
    description="Survey AI agents about any topic"
)
@input_param("topic", str, description="What to ask about")
@input_param("num_agents", int, default=3, min_value=1, max_value=10)
@output_schema({
    "responses": "list",
    "summary": "str"
})
def my_survey(topic, num_agents, ep_api_token):
    # Your EDSL logic
    question = QuestionFreeText(
        question_name="opinion",
        question_text=f"What do you think about {topic}?"
    )
    
    agents = AgentList([Agent() for _ in range(num_agents)])
    results = question.by(agents).run(expected_parrot_api_key=ep_api_token)
    
    return {
        "responses": list(results.to_dict()),
        "summary": f"Asked {num_agents} agents about {topic}"
    }

# Run locally
if __name__ == "__main__":
    from edsl.extensions import run_service
    run_service(my_survey, port=8000)
```

## Usage

1. **Install**: `pip install "edsl[services]"`
2. **Run**: `python my_survey.py`
3. **Test**: Visit `http://localhost:8000/docs`

## Key Features

- **@edsl_service**: Define service name and description
- **@input_param**: Define parameters with validation
- **@output_schema**: Define return structure
- **Automatic validation**: Types, ranges, required fields
- **Auto-generated docs**: Interactive API documentation
- **Error handling**: Clear error messages

That's it! Focus on your EDSL logic, framework handles the web service.
