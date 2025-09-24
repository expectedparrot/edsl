#!/usr/bin/env python3
"""
Profile 100 interviews to identify bottlenecks at scale.
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


def create_test_agents(num_agents=10):
    """Create test agents."""
    agents = []
    occupations = ["teacher", "engineer", "artist", "doctor", "writer", "nurse", "lawyer", "chef", "pilot", "designer"]
    for i in range(num_agents):
        agent = Agent(
            name=f"Person_{i+1}",
            traits={
                "age": 25 + i * 3,
                "occupation": occupations[i % len(occupations)],
                "personality": f"personality_type_{i+1}"
            }
        )
        agents.append(agent)
    return agents


def create_test_scenarios(num_scenarios=10):
    """Create test scenarios."""
    scenarios = []
    settings = ["office", "home", "cafe", "park", "library", "mall", "gym", "beach", "restaurant", "airport"]
    contexts = ["morning", "afternoon", "evening", "night", "weekend"]
    for i in range(num_scenarios):
        scenario = Scenario({
            "context": contexts[i % len(contexts)],
            "setting": settings[i % len(settings)],
            "day_of_week": ["monday", "tuesday", "wednesday", "thursday", "friday"][i % 5]
        })
        scenarios.append(scenario)
    return scenarios


def main():
    """Profile 100 interviews."""
    print("EDSL Job Performance Profiling - 100 Interviews")
    print("=" * 55)
    
    try:
        # Create components for 100 interviews (10 agents × 10 scenarios = 100)
        with timer("Creating survey (2 questions)"):
            q1 = QuestionFreeText(question_text="What is your name?", question_name="name")
            q2 = QuestionMultipleChoice(
                question_text="How are you feeling today?",
                question_options=["Excellent", "Good", "Okay", "Not great", "Terrible"],
                question_name="feeling"
            )
            survey = Survey(questions=[q1, q2])
        
        with timer("Creating test model"):
            model = Model("test")
        
        with timer("Creating 10 agents"):
            agents = create_test_agents(10)
        
        with timer("Creating 10 scenarios"):
            scenarios = create_test_scenarios(10)
        
        with timer("Job construction"):
            job = survey.by(agents).by(scenarios).by(model)
        
        print(f"\nJob created with {len(job)} total interviews")
        
        # Profile the execution
        print("Running cProfile analysis for 100 interviews...")
        
        pr = cProfile.Profile()
        pr.enable()
        
        start_time = time.time()
        results = job.run(
            cache=False,
            progress_bar=False,
            stop_on_exception=False,
            disable_remote_inference=True,
            check_api_keys=False
        )
        end_time = time.time()
        
        pr.disable()
        
        # Results analysis
        execution_time = end_time - start_time
        print(f"\nExecution completed!")
        print(f"Total interviews: {len(results)}")
        print(f"Total execution time: {execution_time:.3f} seconds")
        print(f"Average time per interview: {execution_time/len(results):.4f} seconds")
        print(f"Interviews per second: {len(results)/execution_time:.2f}")
        
        # Generate detailed profiling report
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s)
        ps.sort_stats('cumulative')
        ps.print_stats(25)  # Top 25 functions
        
        print("\n" + "=" * 70)
        print("TOP 25 PERFORMANCE BOTTLENECKS (by cumulative time)")
        print("=" * 70)
        print(s.getvalue())
        
        # EDSL-specific analysis
        s2 = io.StringIO()
        ps2 = pstats.Stats(pr, stream=s2)
        ps2.sort_stats('cumulative')
        ps2.print_stats('edsl', 20)  # Top 20 EDSL functions
        
        print("\n" + "=" * 70)
        print("TOP 20 EDSL-SPECIFIC BOTTLENECKS")
        print("=" * 70)
        print(s2.getvalue())
        
        # Analyze most time-consuming individual functions
        s3 = io.StringIO()
        ps3 = pstats.Stats(pr, stream=s3)
        ps3.sort_stats('tottime')  # Sort by self-time (not cumulative)
        ps3.print_stats(15)
        
        print("\n" + "=" * 70)
        print("FUNCTIONS WITH HIGHEST SELF-TIME (excluding calls to other functions)")
        print("=" * 70)
        print(s3.getvalue())
        
        print(f"\n" + "=" * 70)
        print("PERFORMANCE ANALYSIS & REFACTORING RECOMMENDATIONS")
        print("=" * 70)
        print(f"✓ Processed {len(results)} interviews in {execution_time:.3f} seconds")
        print(f"✓ Average: {execution_time/len(results)*1000:.1f} ms per interview")
        print(f"✓ Throughput: {len(results)/execution_time:.1f} interviews/second")
        
        print("\n🎯 KEY BOTTLENECKS TO ADDRESS:")
        print("1. Prompt construction and rendering appears to be a major bottleneck")
        print("2. Task execution overhead in question_task_creator.py") 
        print("3. Invigilator prompt generation happens repeatedly")
        print("4. Each interview involves significant async overhead")
        
        print("\n🚀 REFACTORING OPPORTUNITIES:")
        print("1. CACHE PROMPT TEMPLATES: prompt_constructor.py:551 and related functions")
        print("   - Pre-render static parts of prompts")
        print("   - Cache instruction prompts that don't change per interview")
        
        print("2. BATCH PROCESSING: question_task_creator.py:234")
        print("   - Process multiple interviews in larger batches")
        print("   - Reduce async task creation overhead")
        
        print("3. OPTIMIZE PROMPT RENDERING: prompt.py:247")
        print("   - Template compilation optimization")
        print("   - Reduce repeated string operations")
        
        print("4. MINIMIZE OBJECT CREATION:")
        print("   - Reuse objects where possible in the interview pipeline")
        print("   - Pool frequently created objects")
        
        print("5. ASYNC OPTIMIZATION:")
        print("   - Review async/await patterns for unnecessary context switching")
        print("   - Consider using asyncio.gather for true parallelism")
        
        return results, execution_time
        
    except Exception as e:
        print(f"Error during profiling: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return None, 0


if __name__ == "__main__":
    main()