import sys
import pkgutil
import importlib
import argparse
import subprocess
import json
from pathlib import Path


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
        
        return {
            "success": True,
            "import_time": end - start,
            "new_module_count": len(new_modules),
            "new_modules": list(new_modules)
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
            print(f"New modules imported: {data['new_module_count']}")
            return data["import_time"], data["new_module_count"]
        else:
            print(f"Error importing {module_name}: {data['error']}")
            return None, None

    except subprocess.CalledProcessError as e:
        print(f"Error running analysis: {e}")
        if e.output:
            print(f"Output: {e.output}")
        return None, None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None, None


def analyze_package(package_name):
    """Analyze all modules in a package."""
    try:
        # Import the base package
        package = importlib.import_module(package_name)
    except ImportError as e:
        print(f"Error: Could not import package {package_name}")
        print(f"Error details: {str(e)}")
        return

    if not hasattr(package, "__path__"):
        print(f"Error: {package_name} is not a package (no __path__ attribute)")
        return

    # Create the analysis script
    script_path = create_analysis_script()

    try:
        modules = []
        for _, name, _ in pkgutil.iter_modules(package.__path__):
            full_name = f"{package_name}.{name}"
            modules.append(full_name)

        print(f"Found {len(modules)} modules to analyze in {package_name}")

        results = []
        for module_name in sorted(modules):
            import_time, new_module_count = analyze_module_import(
                module_name, script_path
            )
            if import_time is not None:
                results.append((module_name, import_time, new_module_count))

        if not results:
            print("\nNo successful module imports to report.")
            return

        print("\n\nSUMMARY (sorted by import time)")
        print("=" * 80)
        print(f"{'Module':<50} {'Import Time':<15} {'Dependencies'}")
        print("-" * 80)

        for module_name, import_time, new_module_count in sorted(
            results, key=lambda x: x[1], reverse=True
        ):
            print(f"{module_name:<50} {import_time:>8.4f}s {new_module_count:>8}")

    finally:
        # Clean up the temporary script
        script_path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Analyze module import times and dependencies."
    )
    parser.add_argument(
        "package", help="Package to analyze (e.g., edsl.surveys, pandas.core)"
    )
    args = parser.parse_args()

    analyze_package(args.package)


if __name__ == "__main__":
    main()
