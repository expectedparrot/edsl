import sys
import re
import toml

VERSION_PATH = "edsl/__version__.py"
PYPROJECT_PATH = "pyproject.toml"

def get_version_from_file(path):
    try:
        with open(path, "r") as file:
            if path.endswith(".py"):
                match = re.search(
                    r'__version__ = "(\d+\.\d+\.\d+(\.dev\d+)?)', file.read()
                )
                if match:
                    return match.group(1)
            elif path.endswith(".toml"):
                data = toml.load(file)
                return data["tool"]["poetry"]["version"]
    except FileNotFoundError:
        print(f"Error: File {path} not found.")
        sys.exit(1)
    except toml.TomlDecodeError:
        print(f"Error: Failed to parse TOML in {path}.")
        sys.exit(1)
    print(f"Error: Version not found in {path}.")
    sys.exit(1)

def write_version_to_file(path, version):
    try:
        if path.endswith(".py"):
            with open(path, "w") as file:
                file.write(f'__version__ = "{version}"\n')
        elif path.endswith(".toml"):
            with open(path, "r+") as file:
                data = toml.load(file)
                data["tool"]["poetry"]["version"] = version
                file.seek(0)
                file.truncate()
                toml.dump(data, file)
    except Exception as e:
        print(f"Error writing to {path}: {e}")
        sys.exit(1)

def get_new_version(version, part):
    major, minor, patch, *dev = re.split(r"[.\-]", version)
    if part == "major":
        major = str(int(major) + 1)
        minor, patch = "0", "0"
    elif part == "minor":
        minor = str(int(minor) + 1)
        patch = "0"
    elif part == "patch":
        patch = str(int(patch) + 1)
    elif part == "dev":
        dev = f".dev{int(dev[0][3:]) + 1 if dev else 1}"
        return f"{major}.{minor}.{patch}{dev}"
    elif part == "deploy":
        return f"{major}.{minor}.{patch}"  # Remove the .dev suffix

    return f"{major}.{minor}.{patch}"

def main(part):
    current_version = get_version_from_file(VERSION_PATH)
    current_version_pyproject = get_version_from_file(PYPROJECT_PATH)

    if current_version != current_version_pyproject:
        print(
            f"Version mismatch:\n"
            f"- {VERSION_PATH} has version: {current_version}\n"
            f"- {PYPROJECT_PATH} has {current_version_pyproject}."
        )
        sys.exit(1)

    new_version = get_new_version(current_version, part)
    write_version_to_file(VERSION_PATH, new_version)
    write_version_to_file(PYPROJECT_PATH, new_version)

    print(f"Version updated from {current_version} to {new_version}")

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ["dev", "patch", "minor", "major", "deploy"]:
        print("Usage: make bump [dev|patch|minor|major|deploy]")
        sys.exit(1)

    main(sys.argv[1])
