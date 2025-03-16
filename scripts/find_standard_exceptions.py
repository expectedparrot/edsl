#!/usr/bin/env python3
"""
Script to recursively search through a directory and identify any raised 
standard Python exceptions.
"""

import os
import re
import sys
import builtins

def get_standard_exceptions():
    """Return a list of all standard Python exceptions."""
    return [name for name in dir(builtins) 
            if name.endswith('Error') or name.endswith('Exception') or name == 'BaseException']

def find_raised_exceptions(directory, standard_exceptions):
    """
    Recursively search through a directory for raised standard exceptions.
    
    Args:
        directory: The directory to search through
        standard_exceptions: List of standard Python exception names
    
    Returns:
        Dictionary mapping file paths to lists of (line_number, exception_name, line_content)
    """
    results = {}
    
    # Regular expression to match 'raise ExceptionName' patterns
    exception_pattern = r'raise\s+(?P<exception>[A-Za-z][A-Za-z0-9_]*)(\(|$|\s)'
    
    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith('.py'):
                continue
                
            file_path = os.path.join(root, file)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.readlines()
                
                file_exceptions = []
                for i, line in enumerate(content):
                    matches = re.search(exception_pattern, line)
                    if matches:
                        exception_name = matches.group('exception')
                        if exception_name in standard_exceptions:
                            file_exceptions.append((i+1, exception_name, line.strip()))
                
                if file_exceptions:
                    results[file_path] = file_exceptions
                    
            except Exception as e:
                print(f"Error processing {file_path}: {e}", file=sys.stderr)
    
    return results

def process_file(file_path, standard_exceptions):
    """Process a single file to find standard exceptions."""
    if not file_path.endswith('.py'):
        return {}
    
    results = {}
    
    # Regular expression to match 'raise ExceptionName' patterns
    exception_pattern = r'raise\s+(?P<exception>[A-Za-z][A-Za-z0-9_]*)(\(|$|\s)'
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.readlines()
        
        file_exceptions = []
        for i, line in enumerate(content):
            matches = re.search(exception_pattern, line)
            if matches:
                exception_name = matches.group('exception')
                if exception_name in standard_exceptions:
                    file_exceptions.append((i+1, exception_name, line.strip()))
        
        if file_exceptions:
            results[file_path] = file_exceptions
                
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
    
    return results

def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        directory = os.getcwd()
    else:
        directory = sys.argv[1]
    
    standard_exceptions = get_standard_exceptions()
    results = {}
    
    # Check if the path is a directory or a file
    if os.path.isdir(directory):
        results = find_raised_exceptions(directory, standard_exceptions)
    elif os.path.isfile(directory) and directory.endswith('.py'):
        results = process_file(directory, standard_exceptions)
    else:
        print(f"Error: {directory} is not a valid Python file or directory", file=sys.stderr)
        sys.exit(1)
    
    # Print results
    if not results:
        print(f"No standard exceptions found in {directory}")
        return
    
    print(f"Found standard exceptions in {len(results)} files:")
    for file_path, exceptions in sorted(results.items()):
        if os.path.isdir(directory):
            rel_path = os.path.relpath(file_path, directory)
        else:
            rel_path = file_path
        print(f"\n{rel_path}:")
        for line_num, exception_name, line_content in exceptions:
            print(f"  Line {line_num}: {exception_name} - {line_content}")

if __name__ == "__main__":
    main()