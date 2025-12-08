#!/usr/bin/env python3
"""
Environment Management Script for EDSL

Manages .env files for different environments (testing, prod, dev, etc.)
with bidirectional sync between working .env and source environment files.
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


class EnvManager:
    def __init__(self, base_dir="."):
        self.base_dir = Path(base_dir)
        self.current_file = self.base_dir / ".env.current"
        self.working_env = self.base_dir / ".env"

    def get_env_files(self):
        """Get all .env.* files (excluding .env.current)"""
        env_files = []
        for file_path in self.base_dir.glob(".env.*"):
            if file_path.name != ".env.current":
                env_name = file_path.name[5:]  # Remove ".env." prefix
                env_files.append(env_name)
        return sorted(env_files)

    def get_current_env(self):
        """Get the currently active environment"""
        if self.current_file.exists():
            return self.current_file.read_text().strip()
        return None

    def list_environments(self):
        """List all available environments"""
        env_files = self.get_env_files()
        current_env = self.get_current_env()

        if not env_files:
            print("No environment files found (.env.* pattern)")
            return

        print("Available environments:")
        for env_name in env_files:
            marker = "* " if env_name == current_env else "  "
            suffix = " (current)" if env_name == current_env else ""
            print(f"  {marker}{env_name}{suffix}")

    def show_current(self):
        """Show the currently active environment"""
        current_env = self.get_current_env()
        if current_env:
            print(f"Current environment: {current_env}")
            if self.working_env.exists():
                print(f"Working file: .env")
                print(f"Source file: .env.{current_env}")
        else:
            print("No environment tracking (consider running 'python scripts/env_manager.py switch <name>')")

    def create_environment(self, env_name):
        """Create a new environment file"""
        if not env_name:
            print("Error: Environment name is required")
            sys.exit(1)

        env_file = self.base_dir / f".env.{env_name}"

        if env_file.exists():
            print(f"Environment file .env.{env_name} already exists")
            sys.exit(1)

        if self.working_env.exists():
            shutil.copy2(self.working_env, env_file)
            print(f"Created .env.{env_name} (copied from current .env)")
        else:
            env_file.touch()
            print(f"Created empty .env.{env_name}")

        print(f"Edit .env.{env_name} directly or switch and edit .env:")
        print(f"  python scripts/env_manager.py switch {env_name}")

    def save_current(self):
        """Save current .env back to its source environment file"""
        current_env = self.get_current_env()
        if not current_env:
            print("No active environment to save to (no .env.current file)")
            print("Use 'python scripts/env_manager.py switch <name>' to set an environment first")
            sys.exit(1)

        if not self.working_env.exists():
            print("No .env file to save")
            sys.exit(1)

        source_file = self.base_dir / f".env.{current_env}"
        shutil.copy2(self.working_env, source_file)
        print(f"Saved current .env back to .env.{current_env}")

    def switch_environment(self, env_name):
        """Switch to specified environment with bidirectional sync"""
        if not env_name:
            print("Error: Environment name is required")
            self.list_environments()
            sys.exit(1)

        env_file = self.base_dir / f".env.{env_name}"

        if not env_file.exists():
            print(f"Environment file .env.{env_name} not found")
            print("Available environments:")
            self.list_environments()
            print(f"\nCreate with: python scripts/env_manager.py create {env_name}")
            sys.exit(1)

        # Save current environment if one is active
        current_env = self.get_current_env()
        if current_env and self.working_env.exists():
            current_source = self.base_dir / f".env.{current_env}"
            print(f"Saving current changes from .env to .env.{current_env}")
            shutil.copy2(self.working_env, current_source)

        # Load new environment
        shutil.copy2(env_file, self.working_env)
        self.current_file.write_text(env_name)

        print(f"Switched to environment: {env_name}")
        print("Edit .env as needed - changes will be saved when you switch environments")

    def backup_env(self):
        """Create a timestamped backup of the current .env"""
        if not self.working_env.exists():
            print("No .env file to backup")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.base_dir / f".env.backup.{timestamp}"
        shutil.copy2(self.working_env, backup_file)
        print(f"Current .env backed up to .env.backup.{timestamp}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage EDSL environment files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/env_manager.py list               # List all environments
  python scripts/env_manager.py current            # Show current environment
  python scripts/env_manager.py create testing     # Create new environment
  python scripts/env_manager.py switch testing     # Switch to environment
  python scripts/env_manager.py save               # Save current changes
  python scripts/env_manager.py backup             # Backup current .env
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # List command
    subparsers.add_parser('list', help='List all available environment configurations')

    # Current command
    subparsers.add_parser('current', help='Show the currently active environment')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new environment file')
    create_parser.add_argument('name', help='Name of the environment to create')

    # Switch command
    switch_parser = subparsers.add_parser('switch', help='Switch to specified environment')
    switch_parser.add_argument('name', help='Name of the environment to switch to')

    # Save command
    subparsers.add_parser('save', help='Save current .env back to its source environment file')

    # Backup command
    subparsers.add_parser('backup', help='Create a timestamped backup of current .env')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Change to the project root directory (where Makefile is)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)

    env_manager = EnvManager()

    try:
        if args.command == 'list':
            env_manager.list_environments()
        elif args.command == 'current':
            env_manager.show_current()
        elif args.command == 'create':
            env_manager.create_environment(args.name)
        elif args.command == 'switch':
            env_manager.switch_environment(args.name)
        elif args.command == 'save':
            env_manager.save_current()
        elif args.command == 'backup':
            env_manager.backup_env()
    except KeyboardInterrupt:
        print("\nOperation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()