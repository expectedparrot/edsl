#!/usr/bin/env python3
"""
Test script to demonstrate enhanced job execution logging.

This script shows the detailed timing logs we've added to the Jobs execution process.
"""

import logging
import sys
import os

# Add the edsl package to the path so we can import it
sys.path.insert(0, '/Users/johnhorton/tools/ep/edsl')

from edsl.logger import set_level, get_logger
from edsl import Jobs, QuestionFreeText, Agent, Model, Survey

def test_enhanced_job_logging():
    """Test the enhanced job logging functionality"""
    
    # Set up logging to INFO level so we can see the detailed timing logs
    set_level(logging.INFO)
    
    # Create a console handler so we can see the logs in the terminal
    logger = get_logger(__name__)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # Add handler to the root EDSL logger
    edsl_logger = logging.getLogger("edsl")
    edsl_logger.addHandler(console_handler)
    
    print("Testing enhanced job execution logging...")
    print("=" * 60)
    
    try:
        # Create a simple job with multiple agents to see detailed timing
        survey = Survey(questions=[
            QuestionFreeText(question_name="q1", question_text="What is your favorite color?"),
            QuestionFreeText(question_name="q2", question_text="What is your favorite food?")
        ])
        
        agents = [
            Agent(name="agent1", traits={"personality": "optimistic"}),
            Agent(name="agent2", traits={"personality": "analytical"})
        ]
        
        model = Model("test")  # Using test model for faster execution
        
        job = Jobs(survey=survey, agents=agents, models=[model])
        
        print(f"\n🚀 Running job with {job.num_interviews} interviews...")
        print("Watch for detailed timing logs below:")
        print("-" * 60)
        
        # Run the job with remote inference disabled to see local execution timing
        results = job.run(
            disable_remote_inference=True,
            progress_bar=False,  # Disable progress bar to see cleaner logs
            n=1  # Run once per combination
        )
        
        print("-" * 60)
        print(f"✅ Job completed successfully with {len(results)} results!")
        
    except Exception as e:
        print(f"❌ Error during job execution: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Enhanced logging test completed!")
    print("You should see detailed timing logs above including:")
    print("- Configuration transfer timing")
    print("- Object validation timing")
    print("- Cache setup timing")
    print("- Remote execution check timing")
    print("- Local execution preparation timing")
    print("- Interview runner timing")
    print("- Batch processing timing")
    print("- Individual interview timing (every 10 interviews)")

if __name__ == "__main__":
    test_enhanced_job_logging()
