#!/usr/bin/env python3
"""
Simplified profiling script to identify performance bottlenecks.
"""

import time
import cProfile
import pstats
import io
from contextlib import contextmanager
import traceback
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


def main():
    """Run profiling with proper error handling."""
    print("EDSL Job Performance Profiling Tool")
    print("=" * 50)
    
    try:
        # Create basic components
        print("Creating components...")
        
        with timer("Creating survey"):
            q1 = QuestionFreeText(question_text="What is your name?", question_name="name")
            q2 = QuestionMultipleChoice(
                question_text="How are you feeling?",
                question_options=["Great", "Good", "OK", "Bad"],
                question_name="feeling"
            )
            survey = Survey(questions=[q1, q2])
        
        with timer("Creating model"):
            model = Model("test")
        
        with timer("Creating agents"):
            agents = [
                Agent(name="Person_1", traits={"age": 25, "occupation": "teacher"}),
                Agent(name="Person_2", traits={"age": 30, "occupation": "engineer"}),
            ]
        
        with timer("Creating scenarios"):
            scenarios = [
                Scenario({"context": "morning", "setting": "office"}),
                Scenario({"context": "afternoon", "setting": "home"}),
                Scenario({"context": "evening", "setting": "cafe"}),
            ]
        
        with timer("Creating cache"):
            cache = Cache()
        
        with timer("Job construction"):
            job = survey.by(agents).by(scenarios).by(model)
        
        print(f"\nJob created with {len(job)} total interviews")
        
        # Profile the execution
        print("Running cProfile analysis...")
        
        pr = cProfile.Profile()
        pr.enable()
        
        start_time = time.time()
        results = job.run(
            cache=False,  # Disable cache to avoid service issues
            progress_bar=False,  # Disable progress bar to avoid service issues
            stop_on_exception=False,
            disable_remote_inference=True,
            check_api_keys=False
        )
        end_time = time.time()
        
        pr.disable()
        
        # Results
        execution_time = end_time - start_time
        print(f"\nExecution completed!")
        print(f"Total interviews: {len(results)}")
        print(f"Total execution time: {execution_time:.3f} seconds")
        print(f"Average time per interview: {execution_time/len(results):.3f} seconds")
        
        # Generate profiling report
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s)
        ps.sort_stats('cumulative')
        ps.print_stats(20)  # Top 20 functions
        
        print("\n" + "=" * 60)
        print("TOP PERFORMANCE BOTTLENECKS (by cumulative time)")
        print("=" * 60)
        print(s.getvalue())
        
        # EDSL-specific analysis
        s2 = io.StringIO()
        ps2 = pstats.Stats(pr, stream=s2)
        ps2.sort_stats('cumulative')
        ps2.print_stats('edsl', 15)  # Top 15 EDSL functions
        
        print("\n" + "=" * 60)
        print("EDSL-SPECIFIC BOTTLENECKS")
        print("=" * 60)
        print(s2.getvalue())
        
        # Sample results
        print("\n" + "=" * 60)
        print("SAMPLE RESULTS")
        print("=" * 60)
        for i, result in enumerate(results[:2]):
            print(f"Interview {i+1}:")
            print(f"  Agent: {result.agent.name}")
            print(f"  Scenario: {result.scenario}")
            print(f"  Answers: {result.answer}")
            print()
        
        print("\nPROFILING RECOMMENDATIONS:")
        print("1. Look for functions with high cumulative time")
        print("2. Identify repeated operations that could be cached")
        print("3. Check for synchronous operations that could be async")
        print("4. Look for object creation/serialization overhead")
        
    except Exception as e:
        print(f"Error during profiling: {e}")
        print("\nFull traceback:")
        traceback.print_exc()


if __name__ == "__main__":
    main()