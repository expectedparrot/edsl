#!/usr/bin/env python3
"""
Profile job running with 100 interviews using local test model inference.

This script demonstrates running EDSL jobs with multiple interviews for profiling purposes
and provides detailed timing analysis to identify performance bottlenecks.
Based on patterns found in tests/jobs/test_repair.py and test_multiple_runs.py.
"""

import time
import cProfile
import pstats
import io
from contextlib import contextmanager
from edsl.language_models import Model
from edsl.questions import QuestionFreeText, QuestionMultipleChoice
from edsl.surveys import Survey
from edsl.agents import Agent
from edsl.scenarios import Scenario
from edsl.caching import Cache


@contextmanager
def timer(description):
    """Context manager for timing operations."""
    start = time.time()
    yield
    end = time.time()
    print(f"{description}: {end - start:.3f} seconds")


def create_sample_survey():
    """Create a sample survey with multiple question types."""
    questions = [
        QuestionFreeText(
            question_text="What is your name?", 
            question_name="name"
        ),
        QuestionMultipleChoice(
            question_text="How are you feeling today?",
            question_options=["Great", "Good", "OK", "Not so good", "Bad"],
            question_name="feeling"
        ),
        QuestionFreeText(
            question_text="What are your thoughts on AI?", 
            question_name="ai_thoughts"
        ),
    ]
    return Survey(questions=questions)


def create_test_agents(num_agents=5):
    """Create a list of test agents with different traits."""
    agents = []
    occupations = ["teacher", "engineer", "artist", "doctor", "writer"]
    for i in range(num_agents):
        agent = Agent(
            name=f"Person_{i+1}",
            traits={
                "age": 25 + i * 5,
                "occupation": occupations[i % 5],
                "personality": f"personality_type_{i+1}"
            }
        )
        agents.append(agent)
    return agents


def create_test_scenarios(num_scenarios=20):
    """Create test scenarios."""
    scenarios = []
    for i in range(num_scenarios):
        scenario = Scenario({
            "context": f"Scenario {i+1}",
            "setting": ["office", "home", "park", "cafe", "library"][i % 5],
            "time_of_day": ["morning", "afternoon", "evening", "night"][i % 4]
        })
        scenarios.append(scenario)
    return scenarios


def run_detailed_profiling():
    """Run detailed profiling with cProfile to identify bottlenecks."""
    print("=" * 60)
    print("DETAILED PERFORMANCE PROFILING")
    print("=" * 60)
    
    # Setup
    with timer("Setup (survey, agents, scenarios, model)"):
        survey = create_sample_survey()
        model = Model("test")
        agents = create_test_agents(2)  # Reduced for initial testing
        scenarios = create_test_scenarios(5)  # Reduced for initial testing
        cache = Cache()
    
    # Job creation
    with timer("Job creation"):
        job = survey.by(agents).by(scenarios).by(model)
    
    print(f"Created job with {len(job)} total interviews")
    
    # Profile the job execution
    print("\nRunning cProfile analysis...")
    
    pr = cProfile.Profile()
    pr.enable()
    
    start_time = time.time()
    results = job.run(
        cache=cache,
        progress_bar=False,  # Disable for cleaner profiling
        stop_on_exception=False,
        disable_remote_inference=True,
        check_api_keys=False
    )
    end_time = time.time()
    
    pr.disable()
    
    # Analyze results
    execution_time = end_time - start_time
    print(f"\nTotal execution time: {execution_time:.3f} seconds")
    print(f"Average time per interview: {execution_time/len(results):.3f} seconds")
    
    # Generate profiling report
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s)
    ps.sort_stats('cumulative')
    ps.print_stats(30)  # Top 30 functions
    
    print("\n" + "=" * 60)
    print("TOP PERFORMANCE BOTTLENECKS (by cumulative time)")
    print("=" * 60)
    print(s.getvalue())
    
    # Generate more focused reports
    print("\n" + "=" * 60)
    print("EDSL-SPECIFIC BOTTLENECKS (filtering for edsl modules)")
    print("=" * 60)
    
    s2 = io.StringIO()
    ps2 = pstats.Stats(pr, stream=s2)
    ps2.sort_stats('cumulative')
    ps2.print_stats('edsl', 20)  # Top 20 EDSL functions
    print(s2.getvalue())
    
    return results, execution_time


def run_step_by_step_timing():
    """Run step-by-step timing analysis."""
    print("\n" + "=" * 60)
    print("STEP-BY-STEP TIMING ANALYSIS")
    print("=" * 60)
    
    # Create components with timing
    with timer("Creating survey"):
        survey = create_sample_survey()
    
    with timer("Creating test model"):
        model = Model("test")
    
    with timer("Creating 2 agents"):
        agents = create_test_agents(2)
    
    with timer("Creating 5 scenarios"):
        scenarios = create_test_scenarios(5)
    
    with timer("Creating cache"):
        cache = Cache()
    
    with timer("Job construction (survey.by(agents).by(scenarios).by(model))"):
        job = survey.by(agents).by(scenarios).by(model)
    
    with timer("Generating interviews list"):
        interviews = job.interviews()
    
    print(f"Generated {len(interviews)} interviews")
    
    # Time individual interview execution
    print("\nTiming individual interview execution:")
    individual_times = []
    
    for i in range(min(5, len(interviews))):  # Time first 5 interviews
        interview = interviews[i]
        start = time.time()
        try:
            # Run single interview
            single_job = survey.by(interview.agent).by(interview.scenario).by(model)
            result = single_job.run(
                cache=cache,
                progress_bar=False,
                stop_on_exception=False,
                disable_remote_inference=True,
                check_api_keys=False
            )
            end = time.time()
            individual_times.append(end - start)
            print(f"Interview {i+1}: {end - start:.3f} seconds")
        except Exception as e:
            print(f"Interview {i+1} failed: {e}")
    
    if individual_times:
        avg_individual = sum(individual_times) / len(individual_times)
        print(f"Average individual interview time: {avg_individual:.3f} seconds")
        print(f"Estimated total time for 100 interviews: {avg_individual * 100:.3f} seconds")


def main():
    """Main function to run all profiling analyses."""
    print("EDSL Job Performance Profiling Tool")
    print("This will help identify bottlenecks for refactoring")
    
    # Run step-by-step analysis first
    run_step_by_step_timing()
    
    # Run detailed profiling
    results, execution_time = run_detailed_profiling()
    
    print(f"\n" + "=" * 60)
    print("SUMMARY AND RECOMMENDATIONS")
    print("=" * 60)
    print(f"Total interviews completed: {len(results)}")
    print(f"Total execution time: {execution_time:.3f} seconds")
    print(f"Average time per interview: {execution_time/len(results):.4f} seconds")
    
    print("\nTo identify refactoring opportunities, look for:")
    print("1. Functions with high cumulative time in the profiling output")
    print("2. EDSL modules that appear frequently in the bottlenecks")
    print("3. Any synchronous operations that could be made asynchronous")
    print("4. Repeated work that could be cached or memoized")
    print("5. Object creation/serialization overhead")
    
    return results


if __name__ == "__main__":
    main()