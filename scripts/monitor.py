import psutil
import time
import argparse
from datetime import datetime
import subprocess
import sys
import os


def monitor_script(script_path, args=None, interval=0.1):
    """
    Run and monitor a Python script's memory usage.

    Args:
        script_path: Path to the Python script to monitor
        args: List of arguments to pass to the script
        interval: How often to check memory usage (in seconds)
    """
    # Start the script as a subprocess
    cmd = [sys.executable, script_path] + (args if args else [])
    process = subprocess.Popen(cmd)

    # Get the psutil process object
    p = psutil.Process(process.pid)

    # Print header
    print("\nMonitoring Python script:", script_path)
    print("Time".ljust(25), "Memory (MB)".rjust(12), "CPU %".rjust(8))
    print("-" * 47)

    try:
        # Monitor until the process ends
        while process.poll() is None:
            # Get current timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Get memory usage in MB
            memory = p.memory_info().rss / 1024 / 1024

            # Get CPU usage
            cpu_percent = p.cpu_percent()

            # Print the stats
            print(f"{timestamp}  {memory:10.1f} MB {cpu_percent:7.1f}%")

            # Wait for next interval
            time.sleep(interval)

    except psutil.NoSuchProcess:
        print("\nProcess ended")
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
        process.kill()

    return_code = process.wait()
    print(f"\nScript finished with return code: {return_code}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Monitor memory usage of a Python script"
    )
    parser.add_argument("script", help="Path to the Python script to monitor")
    parser.add_argument("args", nargs="*", help="Arguments to pass to the script")
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=1.0,
        help="Monitoring interval in seconds (default: 1.0)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.script):
        print(f"Error: Script '{args.script}' not found")
        sys.exit(1)

    monitor_script(args.script, args.args, args.interval)
