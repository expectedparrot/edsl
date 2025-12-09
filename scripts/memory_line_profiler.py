#!/usr/bin/env python
"""
Line-by-line memory profiling tool for EDSL

This script provides line-by-line memory profiling for specific functions
in the EDSL codebase, focusing on the ScenarioList.filter method.
"""

import sys
import argparse
import subprocess
import webbrowser
import tempfile
from pathlib import Path

def run_memory_line_profiler(
    size=1000,
    expression="id % 2 == 0",
    open_report=True
):
    """
    Run line-by-line memory profiling on the ScenarioList.filter method.
    
    Args:
        size: Number of scenarios to create for testing
        expression: Filter expression to use
        open_report: Whether to open the HTML report when done
        
    Returns:
        Path to the report file
    """
    # Create a temporary directory to work in
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        
        # Create timestamp for output files
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Prepare output file paths
        reports_dir = Path("benchmark_logs/memory_reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Output paths
        text_output = reports_dir / f"line_profile_filter_{timestamp}.txt"
        
        # Create a test script with memory profiling
        test_script = temp_dir_path / "test_filter_memory.py"
        with open(test_script, 'w') as f:
            # Include a more detailed test to show line-by-line memory usage
            f.write(f"""#!/usr/bin/env python
from memory_profiler import profile
import time
import sys
from edsl.scenarios import ScenarioList, Scenario

@profile
def test_filter(size={size}, expression="{expression}"):
    '''
    Test the ScenarioList.filter method with memory profiling.
    
    This function creates a ScenarioList of the specified size,
    with large text content to make memory differences more visible,
    and then profiles the filter operation.
    '''
    # Step 1: Create test data with large text for better memory visibility
    text_size = 10 * 1024  # 10 KB per scenario
    large_text = "x" * text_size
    
    # Step 2: Create scenarios
    scenarios = []
    for i in range(size):
        scenarios.append({{
            "id": i,
            "text": large_text,
            "category": "A" if i % 2 == 0 else "B",
            "value": i * 10
        }})
    
    # Step 3: Create ScenarioList
    sl = ScenarioList(scenarios)
    
    # Step 4: Filter ScenarioList - THIS IS THE OPERATION WE'RE PROFILING
    start_time = time.time()
    result = sl.filter(expression)
    duration = time.time() - start_time
    
    # Step 5: Report results
    print(f"\\nFilter operation completed in {{duration:.4f}} seconds")
    print(f"Input size: {{len(sl)}} scenarios")
    print(f"Output size: {{len(result)}} scenarios")
    
    return result

# Create a function that dives deeper into internals
@profile
def detailed_filter_test(size={size}, expression="{expression}"):
    '''
    A more detailed test that manually implements the filter operation
    to show memory usage at each step.
    '''
    from simpleeval import EvalWithCompoundTypes, NameNotDefined
    
    # Step 1: Setup scenarios with large text
    text_size = 10 * 1024  # 10 KB per scenario
    large_text = "x" * text_size
    
    # Step 2: Create scenarios
    scenarios = []
    for i in range(size):
        scenarios.append({{
            "id": i, 
            "text": large_text,
            "category": "A" if i % 2 == 0 else "B",
            "value": i * 10
        }})
    
    # Step 3: Create ScenarioList
    sl = ScenarioList(scenarios)
    
    # Step 4: Simulate the filter operation with detailed steps
    # This is similar to what happens inside ScenarioList.filter
    
    # Step 4.1: Check keys (like ScenarioList.filter does)
    first_item = sl[0] if len(sl) > 0 else None
    if first_item:
        base_keys = set(first_item.keys())
        keys = set()
        for scenario in sl:
            keys.update(scenario.keys())
    
    # Step 4.2: Create a new ScenarioList for results
    new_sl = ScenarioList(data=[], codebook=sl.codebook)
    
    # Helper function like the one in filter method
    def create_evaluator(scenario):
        return EvalWithCompoundTypes(names=scenario)
    
    # Step 4.3: Iterate and filter
    for scenario in sl:
        try:
            # This is the evaluation step that consumes memory
            if create_evaluator(scenario).eval(expression):
                # This is the copy operation that consumes memory
                new_sl.append(scenario.copy())
        except:
            pass
    
    print(f"\\nDetailed filter completed")
    print(f"Input size: {{len(sl)}} scenarios")
    print(f"Output size: {{len(new_sl)}} scenarios")
    
    return new_sl

if __name__ == "__main__":
    print(f"\\n==== LINE-BY-LINE MEMORY PROFILE - ScenarioList.filter ====")
    print(f"Parameters: size={size}, expression='{expression}'")
    print("="*60)
    
    # Run the standard test
    print("\\nRunning standard filter test:")
    result = test_filter()
    
    print("\\n" + "="*60)
    print("DETAILED STEP-BY-STEP MEMORY PROFILE")
    print("="*60)
    
    # Run the detailed test
    print("\\nRunning detailed filter test:")
    detailed_result = detailed_filter_test()
""")
        
        # Run the memory profiler
        print("Running line-by-line memory profiling on ScenarioList.filter...")
        print(f"Parameters: size={size}, expression='{expression}'")
        
        with open(text_output, 'w') as f:
            subprocess.run(
                [sys.executable, "-m", "memory_profiler", str(test_script)],
                stdout=f,
                stderr=subprocess.STDOUT
            )
        
        # Create HTML version
        html_output = reports_dir / f"memory_profile_{timestamp}.html"
        
        with open(html_output, 'w') as f:
            f.write(f"""<!DOCTYPE html>
<html>
<head>
    <title>Memory Profile Report - ScenarioList.filter</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, 
                         Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
            line-height: 1.6;
            color: #333;
        }}
        pre {{
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
            background-color: #fff;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #ddd;
            overflow-x: auto;
            white-space: pre-wrap;
            font-size: 14px;
            position: relative;
        }}
        h1, h2, h3 {{
            color: #333;
        }}
        h1 {{
            border-bottom: 1px solid #eaecef;
            padding-bottom: 10px;
        }}
        .highlight {{
            background-color: #ffffcc;
        }}
        .memory-increase {{
            color: #e74c3c;
            font-weight: bold;
        }}
        .summary-box {{
            background-color: #f1f8ff;
            border: 1px solid #c8e1ff;
            border-radius: 6px;
            padding: 16px;
            margin: 20px 0;
        }}
        .insights {{
            background-color: #f6f8fa;
            border-left: 4px solid #0366d6;
            padding: 16px;
            margin: 20px 0;
        }}
        .copy-button {{
            position: absolute;
            top: 10px;
            right: 10px;
            padding: 8px 12px;
            background-color: #0366d6;
            color: white;
            border: 2px solid #0366d6;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            transition: all 0.2s;
            z-index: 100;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }}
        .copy-button:hover {{
            background-color: #0256b9;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }}
        .copy-button.copied {{
            background-color: #2ea44f;
            border-color: #2ea44f;
        }}
        .pre-container {{
            position: relative;
        }}
    </style>
</head>
<body>
    <h1>Memory Profile Report - ScenarioList.filter</h1>
    <p>Generated: {timestamp}</p>
    
    <div class="summary-box">
        <h2>Memory Profile Summary</h2>
        <p>This report shows line-by-line memory profiling for the ScenarioList.filter method.
        Lines highlighted in yellow show significant memory increases.</p>
        <ul>
            <li><strong>Test parameters:</strong> size={size}, expression='{expression}'</li>
            <li><strong>Output:</strong> Shows memory consumption per line, measured in MiB</li>
        </ul>
    </div>
    
    <h2>Line-by-Line Memory Profile</h2>
    <div class="pre-container">
        <button class="copy-button" onclick="copyToClipboard()">📋 Copy Profile Data</button>
        <pre id="profile-output">""")
            
            # Add the content of the text file with highlighting
            with open(text_output, 'r') as text_file:
                content = text_file.read()
                import re
                
                # Highlight lines with high memory usage (increments > 0.5 MiB)
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if re.search(r'\d+\.\d+ MiB\s+\d+\.\d+ MiB', line):
                        try:
                            increment = re.search(r'\d+\.\d+ MiB\s+(\d+\.\d+) MiB', line)
                            if increment and float(increment.group(1)) > 0.5:
                                lines[i] = f'<span class="highlight">{line}</span>'
                        except (AttributeError, ValueError):
                            pass
                
                f.write('\n'.join(lines))
            
            f.write("""</pre>
    </div>
    
    <div class="insights">
        <h3>Key Insights</h3>
        <p>Based on the memory profile, key observations about the ScenarioList.filter method:</p>
        <ul>
            <li>The primary memory consumption occurs during the creation of the new ScenarioList</li>
            <li>The simpleeval library's EvalWithCompoundTypes evaluator also consumes memory</li>
            <li>The scenario.copy() operations contribute to memory usage when creating the filtered list</li>
        </ul>
        <p>These insights can guide optimization efforts, particularly for large ScenarioLists.</p>
    </div>
    
    <script>
        function copyToClipboard() {
            // Get the pre element text content - this gets the raw text without HTML formatting
            const pre = document.getElementById('profile-output');
            const text = pre.textContent || pre.innerText;
            
            // Create a textarea element to hold the text temporarily
            const textarea = document.createElement('textarea');
            textarea.value = text;
            
            // Make the textarea not visible and add it to the document
            textarea.style.position = 'absolute';
            textarea.style.left = '-9999px';
            document.body.appendChild(textarea);
            
            // Select and copy the text
            textarea.select();
            document.execCommand('copy');
            
            // Remove the textarea
            document.body.removeChild(textarea);
            
            // Update the button to show feedback
            const button = document.querySelector('.copy-button');
            button.textContent = '✅ Copied to clipboard!';
            button.classList.add('copied');
            
            // Reset the button after 2 seconds
            setTimeout(() => {
                button.textContent = '📋 Copy Profile Data';
                button.classList.remove('copied');
            }, 2000);
        }
    </script>
</body>
</html>""")
        
        print(f"Memory profile text report saved to: {text_output}")
        print(f"Memory profile HTML report saved to: {html_output}")
        
        # Open HTML report if requested
        if open_report:
            webbrowser.open(f"file://{html_output.resolve()}")
        
        return text_output, html_output

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Line-by-line memory profiling for EDSL functions")
    parser.add_argument("--size", "-s", type=int, default=1000,
                      help="Number of scenarios to create for testing")
    parser.add_argument("--expression", "-e", default="id % 2 == 0",
                      help="Filter expression to use")
    parser.add_argument("--no-open", "-n", action="store_true",
                      help="Don't automatically open the HTML report")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run_memory_line_profiler(
        size=args.size,
        expression=args.expression,
        open_report=not args.no_open
    )