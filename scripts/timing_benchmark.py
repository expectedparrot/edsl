#!/usr/bin/env python
"""
EDSL Performance Benchmarks

This script measures performance characteristics of the EDSL library:
1. Import time
2. Survey creation time
3. Model inference time

Results are saved to a log file for historical tracking.
"""

import time
import datetime
import json
import argparse
from pathlib import Path
import matplotlib.pyplot as plt

# Import EDSL components at module level to avoid timing import overhead in benchmarks
from edsl import Survey, QuestionMultipleChoice
from edsl.caching import Cache
from edsl.language_models import LanguageModel

# Constants
LOG_DIR = Path(".") / "benchmark_logs"
LOG_FILE = LOG_DIR / "timing_log.jsonl"
RESULTS_FILE = LOG_DIR / "latest_results.json"


def timed(func):
    """Decorator to time function execution."""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        execution_time = end - start
        return execution_time, result
    return wrapper


@timed
def benchmark_import():
    """Benchmark the time it takes to import edsl."""
    return None


@timed
def benchmark_star_import():
    """Benchmark the time it takes to import everything from edsl."""
    # Import must be done at module level, so we use exec
    namespace = {}
    exec("from edsl import *", namespace)
    return None


@timed
def create_large_survey(num_questions=1000):
    """Create a survey with many questions and measure performance."""
    questions = []
    for i in range(num_questions):
        q = QuestionMultipleChoice(
            question_name=f"q_{i}",
            question_text=f"This is question {i}",
            question_options=[f"Option {j}" for j in range(5)]
        )
        questions.append(q)
    
    survey = Survey(questions=questions)
    return survey


@timed
def render_survey_prompts(survey):
    """Measure how long it takes to render all prompts in a survey."""
    # for question in survey.questions:
    #     # Access prompt to force rendering
    #     _ = question.prompt
    survey.to_jobs().prompts()
    return None


@timed
def run_survey_with_test_model(survey, num_questions=10):
    """Run a survey with a test model and measure performance."""
    # Use a subset of questions if needed
    if len(survey.questions) > num_questions:
        small_survey = Survey(questions=survey.questions[:num_questions])
    else:
        small_survey = survey

    c = Cache()
    m = LanguageModel.example(test_model=True, canned_response="Option 0")

    #m = Model('test', canned_response = "Option 0")
    # Run with test model (no real API calls)
    results = small_survey.by(m).run(disable_remote_inference = True, disable_remote_cache = True, cache = c)
    return results


def run_benchmarks(args):
    """Run all benchmarks and collect results."""
    results = {
        "timestamp": datetime.datetime.now().isoformat(),
        "benchmarks": {}
    }
    
    print("Running EDSL performance benchmarks...")
    
    # Import timing
    import_time, _ = benchmark_import()
    results["benchmarks"]["import_edsl"] = import_time
    print(f"Time to import edsl: {import_time:.4f}s")
    
    star_import_time, _ = benchmark_star_import()
    results["benchmarks"]["star_import"] = star_import_time
    print(f"Time to star import edsl: {star_import_time:.4f}s")
    
    # Survey creation
    num_questions = args.num_questions
    survey_creation_time, survey = create_large_survey(num_questions)
    results["benchmarks"][f"create_{num_questions}_question_survey"] = survey_creation_time
    print(f"Time to create {num_questions} question survey: {survey_creation_time:.4f}s")
    
    # Prompt rendering
    prompt_time, _ = render_survey_prompts(survey)
    results["benchmarks"][f"render_{num_questions}_question_prompts"] = prompt_time
    print(f"Time to render {num_questions} question prompts: {prompt_time:.4f}s")
    
    # Test model run
    test_questions = min(10, args.num_questions)
    model_time, _ = run_survey_with_test_model(survey, test_questions)
    results["benchmarks"][f"run_{test_questions}_questions_with_test_model"] = model_time
    print(f"Time to run {test_questions} questions with test model: {model_time:.4f}s")
    
    # Add platform info
    import platform
    import sys
    results["system_info"] = {
        "platform": platform.platform(),
        "python_version": sys.version,
    }
    
    # Record EDSL version
    try:
        import edsl
        results["edsl_version"] = edsl.__version__
    except (ImportError, AttributeError):
        results["edsl_version"] = "unknown"
    
    return results


def save_results(results):
    """Save benchmark results to log files."""
    # Ensure directory exists
    LOG_DIR.mkdir(exist_ok=True)
    
    # Append to log file
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(results) + "\n")
    
    # Save latest results
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to {LOG_FILE}")


def plot_history():
    """Plot historical benchmark data."""
    if not LOG_FILE.exists():
        print(f"No history found at {LOG_FILE}")
        return
    
    data = []
    with open(LOG_FILE, "r") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    
    if not data:
        print("No benchmark data found.")
        return
    
    # Get common benchmarks
    benchmark_keys = set()
    for entry in data:
        benchmark_keys.update(entry.get("benchmarks", {}).keys())
    
    # Create plot for each benchmark
    fig, axes = plt.subplots(len(benchmark_keys), 1, figsize=(10, 3*len(benchmark_keys)))
    if len(benchmark_keys) == 1:
        axes = [axes]
    
    for ax, key in zip(axes, sorted(benchmark_keys)):
        times = []
        dates = []
        for entry in data:
            if key in entry.get("benchmarks", {}):
                times.append(entry["benchmarks"][key])
                dates.append(datetime.datetime.fromisoformat(entry["timestamp"]))
        
        if times:
            ax.plot(dates, times, 'o-')
            ax.set_title(f"Benchmark: {key}")
            ax.set_ylabel("Time (s)")
            ax.grid(True)
    
    plt.tight_layout()
    plot_path = LOG_DIR / "benchmark_history.png"
    plt.savefig(plot_path)
    print(f"Plot saved to {plot_path}")


def run_pyinstrument(args):
    """Run benchmarks under pyinstrument for profiling."""
    try:
        from pyinstrument import Profiler
    except ImportError:
        print("pyinstrument not installed. Install with: pip install pyinstrument")
        return
    
    profiler = Profiler()
    profiler.start()
    
    results = run_benchmarks(args)
    
    profiler.stop()
    
    # Save profile results
    LOG_DIR.mkdir(exist_ok=True)
    profile_path = LOG_DIR / f"profile_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(profile_path, "w") as f:
        f.write(profiler.output_html())
    
    print(f"Profile saved to {profile_path}")
    return results


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="EDSL Performance Benchmarks")
    parser.add_argument("--num-questions", type=int, default=1000,
                        help="Number of questions to create for benchmarks")
    parser.add_argument("--plot", action="store_true",
                        help="Plot historical benchmark data")
    parser.add_argument("--profile", action="store_true",
                        help="Run with pyinstrument profiling")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    if args.plot:
        plot_history()
    elif args.profile:
        results = run_pyinstrument(args)
        if results:
            save_results(results)
    else:
        results = run_benchmarks(args)
        save_results(results)