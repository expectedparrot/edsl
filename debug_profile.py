#!/usr/bin/env python3
"""
Debug version of the profiling script to identify issues.
"""

import time
import traceback
from edsl.language_models import Model
from edsl.questions import QuestionFreeText, QuestionMultipleChoice
from edsl.surveys import Survey
from edsl.agents import Agent
from edsl.scenarios import Scenario
from edsl.caching import Cache


def simple_test():
    """Simple test to see what's working."""
    print("Starting simple test...")
    
    try:
        print("Creating question...")
        q = QuestionFreeText(question_text="What is your name?", question_name="name")
        print("✓ Question created")
        
        print("Creating model...")
        model = Model("test")
        print("✓ Model created")
        
        print("Creating cache...")
        cache = Cache()
        print("✓ Cache created")
        
        print("Creating simple job...")
        job = q.by(model)
        print("✓ Job created")
        
        print("Running single interview...")
        results = job.run(
            cache=cache,
            progress_bar=False,
            stop_on_exception=True,  # Stop on first exception to see what's failing
            disable_remote_inference=True,
            check_api_keys=False
        )
        print("✓ Job completed successfully!")
        print(f"Results: {len(results)} interviews")
        print(f"First result: {results[0]}")
        
    except Exception as e:
        print(f"✗ Error occurred: {e}")
        print("Full traceback:")
        traceback.print_exc()


def test_multiple_interviews():
    """Test with multiple interviews to see where it fails."""
    print("\nTesting multiple interviews...")
    
    try:
        q = QuestionFreeText(question_text="What is your name?", question_name="name")
        model = Model("test")
        
        # Create 2 agents
        agents = [
            Agent(name="Alice", traits={"occupation": "teacher"}),
            Agent(name="Bob", traits={"occupation": "engineer"})
        ]
        
        cache = Cache()
        job = q.by(agents).by(model)
        
        print(f"Job has {len(job)} interviews")
        
        results = job.run(
            cache=cache,
            progress_bar=False,
            stop_on_exception=True,
            disable_remote_inference=True,
            check_api_keys=False
        )
        
        print("✓ Multiple interview job completed!")
        print(f"Results: {len(results)} interviews")
        
    except Exception as e:
        print(f"✗ Multiple interview error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    simple_test()
    test_multiple_interviews()