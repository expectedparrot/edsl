import sys
import argparse
import json
from pathlib import Path
import subprocess


def create_analysis_script():
    """Create a temporary script that will analyze a single module."""
    script = '''
import time
import sys
import importlib
import json

def analyze_single_module(module_name):
    """Analyze import time and dependencies for a single module."""
    initial_modules = set(sys.modules.keys())
    
    start = time.time()
    try:
        importlib.import_module(module_name)
        end = time.time()
        
        final_modules = set(sys.modules.keys())
        new_modules = final_modules - initial_modules
        
        # Sort modules for consistent output
        sorted_modules = sorted(new_modules)
        
        return {
            "success": True,
            "import_time": end - start,
            "new_module_count": len(new_modules),
            "new_modules": sorted_modules
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    module_name = sys.argv[1]
    result = analyze_single_module(module_name)
    print(json.dumps(result))
'''

    script_path = Path("analyze_single.py")
    script_path.write_text(script)
    return script_path


def analyze_module_import(module_name, script_path):
    """Analyze the import time and dependencies of a module using a subprocess."""
    print(f"\n{'='*60}")
    print(f"Analyzing {module_name}")
    print(f"{'='*60}")

    try:
        # Run the analysis in a separate process
        result = subprocess.run(
            [sys.executable, str(script_path), module_name],
            capture_output=True,
            text=True,
            check=True,
        )

        data = json.loads(result.stdout)

        if data["success"]:
            print(f"\nImport time: {data['import_time']:.4f} seconds")
            print(f"Number of new modules imported: {data['new_module_count']}")
            print("\nNewly imported modules:")
            print("-" * 60)
            for module in data["new_modules"]:
                print(f"- {module}")
            return data
        else:
            print(f"Error importing {module_name}: {data['error']}")
            return None

    except subprocess.CalledProcessError as e:
        print(f"Error running analysis: {e}")
        if e.output:
            print(f"Output: {e.output}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a single module's import time and dependencies."
    )
    parser.add_argument("module", help="Module to analyze (e.g., pandas.core.frame)")
    args = parser.parse_args()

    # Create the analysis script
    script_path = create_analysis_script()

    try:
        analyze_module_import(args.module, script_path)
    finally:
        # Clean up the temporary script
        script_path.unlink()


if __name__ == "__main__":
    main()
