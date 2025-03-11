import re
import os

def remove_breakpoints(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
    
    # Remove both active and commented breakpoints
    new_lines = []
    for line in lines:
        # Skip lines that are just breakpoint() or #breakpoint() with optional whitespace
        if re.match(r'^\s*#?\s*breakpoint\(\)\s*$', line):
            continue
        new_lines.append(line)
    
    # Write the file back only if changes were made
    if len(new_lines) != len(lines):
        with open(file_path, 'w') as file:
            file.writelines(new_lines)
        return True
    return False

def main():
    # Get the root directory
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Walk through all Python files
    files_modified = 0
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if remove_breakpoints(file_path):
                    print(f"Removed breakpoints from: {file_path}")
                    files_modified += 1
    
    print(f"\nTotal files modified: {files_modified}")

if __name__ == "__main__":
    main() 