#!/usr/bin/env python
"""
EDSL Component-Level Benchmarks

This script provides detailed timing measurements for specific EDSL components
to help identify performance bottlenecks.
"""

import time
import datetime
import json
import argparse
from pathlib import Path
import importlib
import sys

# Constants
LOG_DIR = Path(".") / "benchmark_logs"
COMPONENT_LOG_FILE = LOG_DIR / "component_timing_log.jsonl"


def timed(func):
    """Decorator to time function execution."""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        execution_time = end - start
        return execution_time, result
    return wrapper


def benchmark_module_import(module_name):
    """Benchmark importing a specific module."""
    @timed
    def import_module():
        importlib.import_module(module_name)
        return None
    
    return import_module()


def benchmark_all_submodules():
    """Benchmark importing each major EDSL submodule."""
    results = {}
    
    # Define key submodules to benchmark
    submodules = [
        "edsl.questions",
        "edsl.surveys",
        "edsl.agents",
        "edsl.language_models",
        "edsl.jobs",
        "edsl.scenarios",
        "edsl.results",
        "edsl.interviews",
        "edsl.dataset",
        "edsl.caching",
        "edsl.prompts",
        "edsl.utilities",
        "edsl.inference_services",
    ]
    
    for module in submodules:
        try:
            # Clear the module from sys.modules if it's already imported
            if module in sys.modules:
                del sys.modules[module]
            
            time_taken, _ = benchmark_module_import(module)
            results[f"import_{module}"] = time_taken
            print(f"Time to import {module}: {time_taken:.4f}s")
        except Exception as e:
            print(f"Error importing {module}: {e}")
            results[f"import_{module}"] = "error"
    
    return results


@timed
def benchmark_question_types():
    """Benchmark creating different question types."""
    from edsl.questions import (
        QuestionMultipleChoice, QuestionFreeText, QuestionCheckBox,
        QuestionNumerical, QuestionList, QuestionBudget
    )
    
    questions = []
    
    # Create 100 questions of each type
    for i in range(100):
        # Multiple choice
        q1 = QuestionMultipleChoice(
            name=f"mc_{i}", 
            question=f"Multiple choice question {i}", 
            options=[f"Option {j}" for j in range(5)]
        )
        
        # Free text
        q2 = QuestionFreeText(
            name=f"ft_{i}",
            question=f"Free text question {i}"
        )
        
        # Checkbox
        q3 = QuestionCheckBox(
            name=f"cb_{i}",
            question=f"Checkbox question {i}",
            options=[f"Option {j}" for j in range(5)]
        )
        
        # Numerical
        q4 = QuestionNumerical(
            name=f"num_{i}",
            question=f"Numerical question {i}"
        )
        
        # List
        q5 = QuestionList(
            name=f"list_{i}",
            question=f"List question {i}"
        )
        
        # Budget
        q6 = QuestionBudget(
            name=f"budget_{i}",
            question=f"Budget question {i}",
            options=[f"Option {j}" for j in range(5)],
            budget=100
        )
        
        questions.extend([q1, q2, q3, q4, q5, q6])
    
    return questions


@timed
def benchmark_large_survey_dag():
    """Benchmark creating a large survey with a complex DAG."""
    from edsl import Survey, QuestionMultipleChoice, Rule
    
    # Create 100 questions
    questions = []
    for i in range(100):
        q = QuestionMultipleChoice(
            name=f"q_{i}",
            question=f"This is question {i}",
            options=[f"Option {j}" for j in range(5)]
        )
        questions.append(q)
    
    # Create a survey with branching logic
    survey = Survey(questions=questions)
    
    # Add some skip logic
    for i in range(0, 98, 2):
        # If the answer to question i is Option 0, skip the next question
        rule = Rule(
            name=f"skip_rule_{i}",
            condition=f"q_{i} == 'Option 0'",
            action=f"skip q_{i+1}"
        )
        survey.add_rule(rule)
    
    return survey


@timed
def benchmark_model_setup():
    """Benchmark setting up various language models."""
    from edsl.language_models import (
        LanguageModel, AnthropicLanguageModel, OpenAILanguageModel, 
        TestLanguageModel
    )
    
    models = []
    
    # Create instances of various models
    models.append(LanguageModel())
    models.append(AnthropicLanguageModel("claude-3-opus-20240229"))
    models.append(OpenAILanguageModel("gpt-4-turbo"))
    models.append(TestLanguageModel())
    
    return models


@timed
def benchmark_scenario_creation(size=1000):
    """Benchmark creating a large scenario list."""
    from edsl import ScenarioList
    
    scenarios = []
    for i in range(size):
        scenario = {
            "title": f"Scenario {i}",
            "description": f"This is scenario number {i} with a detailed description of what it contains.",
            "data": {
                "id": i,
                "value": i * 10,
                "tags": [f"tag_{j}" for j in range(5)]
            }
        }
        scenarios.append(scenario)
    
    scenario_list = ScenarioList(scenarios)
    return scenario_list


def run_component_benchmarks(args):
    """Run all component benchmarks and collect results."""
    LOG_DIR.mkdir(exist_ok=True)
    
    results = {
        "timestamp": datetime.datetime.now().isoformat(),
        "components": {}
    }
    
    print("Running EDSL component benchmarks...")
    
    # Import all submodules
    submodule_times = benchmark_all_submodules()
    results["components"].update(submodule_times)
    
    # Question types benchmark
    question_time, questions = benchmark_question_types()
    results["components"]["create_600_questions"] = question_time
    print(f"Time to create 600 questions: {question_time:.4f}s")
    
    # Survey DAG benchmark
    dag_time, survey = benchmark_large_survey_dag()
    results["components"]["create_survey_with_dag"] = dag_time
    print(f"Time to create survey with complex DAG: {dag_time:.4f}s")
    
    # Model setup benchmark
    model_time, models = benchmark_model_setup()
    results["components"]["setup_language_models"] = model_time
    print(f"Time to set up language models: {model_time:.4f}s")
    
    # Scenario creation benchmark
    scenario_time, scenarios = benchmark_scenario_creation(args.scenario_size)
    results["components"][f"create_{args.scenario_size}_scenarios"] = scenario_time
    print(f"Time to create {args.scenario_size} scenarios: {scenario_time:.4f}s")
    
    # Add system info
    import platform
    import sys
    results["system_info"] = {
        "platform": platform.platform(),
        "python_version": sys.version,
    }
    
    # Add EDSL version
    try:
        import edsl
        results["edsl_version"] = edsl.__version__
    except (ImportError, AttributeError):
        results["edsl_version"] = "unknown"
    
    # Save results
    with open(COMPONENT_LOG_FILE, "a") as f:
        f.write(json.dumps(results) + "\n")
    
    print(f"Component benchmark results saved to {COMPONENT_LOG_FILE}")
    return results


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="EDSL Component Benchmarks")
    parser.add_argument("--scenario-size", type=int, default=1000,
                        help="Number of scenarios to create for benchmarking")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_component_benchmarks(args)