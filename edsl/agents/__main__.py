"""CLI for the agents module.

This module provides a command-line interface for working with AgentList objects.
Run with: python -m edsl.agents FILE
"""

import sys
import code
from pathlib import Path

from .agent_list import AgentList


def main():
    """Load agents from a file and start an interactive REPL."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Load agents from a file and start an interactive REPL",
        epilog="The AgentList will be available in the REPL as 'agent_list'",
    )
    parser.add_argument(
        "file",
        help="Path to the data file (CSV, Excel, TSV, etc.)",
    )
    parser.add_argument(
        "-s",
        "--source-type",
        help="Source type (csv, excel, tsv, etc.). If not provided, will be inferred from file extension.",
    )
    parser.add_argument(
        "-n",
        "--name-field",
        help="The name of the field to use as the agent name",
    )
    parser.add_argument(
        "-i",
        "--instructions",
        help="Instructions to apply to all agents",
    )
    parser.add_argument(
        "-c",
        "--codebook",
        help="Path to codebook CSV file",
    )

    args = parser.parse_args()

    file_path = Path(args.file)

    if not file_path.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    # Infer source type from file extension if not provided
    source_type = args.source_type
    if source_type is None:
        extension = file_path.suffix.lower()
        extension_map = {
            ".csv": "csv",
            ".tsv": "tsv",
            ".tsx": "tsv",
            ".xlsx": "excel",
            ".xls": "excel",
        }
        source_type = extension_map.get(extension)
        if source_type is None:
            print(
                f"Error: Could not infer source type from extension '{extension}'. "
                f"Please specify --source-type explicitly.",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Loading agents from {args.file} (source type: {source_type})...")

    try:
        agent_list = AgentList.from_source(
            source_type,
            str(file_path),
            name_field=args.name_field,
            instructions=args.instructions,
            codebook=args.codebook,
        )
    except Exception as e:
        print(f"Error loading file: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(agent_list)} agent(s)")

    # Show a sample of traits if available
    if len(agent_list) > 0 and agent_list[0].traits:
        trait_keys = list(agent_list[0].traits.keys())
        print(f"Agent traits: {', '.join(trait_keys)}")

    print("\nStarting REPL...")
    print("The AgentList is available as 'agent_list'\n")

    # Create a local namespace with agent_list available
    local_vars = {
        "agent_list": agent_list,
        "AgentList": AgentList,
    }

    # Start the interactive console
    banner = f"""Python {sys.version} on {sys.platform}
Type "help", "copyright", "credits" or "license" for more information.

AgentList loaded with {len(agent_list)} agent(s) and available as 'agent_list'
"""

    code.interact(banner=banner, local=local_vars, exitmsg="\nExiting REPL...")


if __name__ == "__main__":
    main()
