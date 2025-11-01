#!/usr/bin/env python3
"""
Standalone EDSL App Creator

This version detects if running within Claude Code and provides appropriate guidance.
When run outside Claude Code, it uses the Claude Code SDK to generate apps.
When run inside Claude Code, it provides instructions for using Claude directly.
"""

import os
import sys
import asyncio
from pathlib import Path


def detect_claude_code_environment():
    """Detect if we're running inside Claude Code"""
    # Simple heuristic: if we're in a Claude Code session, certain patterns will exist
    indicators = [
        # Check if parent process might be Claude Code
        lambda: "claude" in str(os.getppid()),
        # Check current working directory patterns
        lambda: "claude" in os.getcwd().lower(),
        # Check environment variables
        lambda: any(var for var in os.environ.keys() if "claude" in var.lower()),
        # Check if stdout/stderr are being captured (common in CLI tools)
        lambda: not os.isatty(sys.stdout.fileno()),
    ]

    claude_score = sum(1 for check in indicators if check())
    return claude_score >= 2  # If multiple indicators, likely in Claude Code


def show_usage_instructions():
    """Show instructions for using the app creator"""
    print(
        """
🤖 Claude EDSL App Creator

This tool creates EDSL apps using the Claude Code SDK.

🔍 DETECTED: You appear to be running inside a Claude Code session.

The Claude Code SDK cannot create new sessions from within an existing session.
Instead, you can:

1️⃣  Ask Claude directly in this session:
   "Please create an EDSL app that [your description here]"

2️⃣  Exit Claude Code and run this script from a terminal:
   python standalone_app_creator.py "description" "app_name"

3️⃣  Use the simple pattern-based creator:
   python simple_edsl_app_creator.py "description" "app_name"

Example request for Claude:
"Please create an EDSL app that takes AgentList as input and generation instructions,
then augments each agent's scenario with generated content based on their characteristics."
"""
    )


async def create_app_with_sdk(description: str, app_name: str):
    """Create app using Claude Code SDK (when not in Claude Code session)"""
    try:
        from claude_code_sdk import query, ClaudeCodeOptions

        # Configure options
        options = ClaudeCodeOptions(
            system_prompt="""You are an expert EDSL app developer. Create high-quality EDSL applications based on descriptions.

Your task:
1. Read the EDSL App Development Guide at examples/EDSL_App_Development_Guide.md
2. Study 2-3 relevant example apps for patterns
3. Create a complete, working EDSL app following established conventions
4. Test the app and fix any issues

Focus on production-ready code that follows EDSL patterns.""",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            permission_mode="acceptEdits",
            max_turns=20,
        )

        # Create comprehensive prompt
        prompt = f"""
Create a complete EDSL app based on this description: "{description}"

Requirements:
- App name: {app_name}
- File: examples/{app_name}.py
- Follow EDSL patterns from the development guide and examples
- Include proper imports, initial_survey, jobs_object, output_formatters
- Add test example in if __name__ == "__main__": block
- Handle AgentList input if mentioned in description
- Return scenarios augmented with generated content

Please analyze the requirements, study existing patterns, create the app, and test it.
"""

        print(f"🚀 Creating EDSL app: {app_name}")
        print(f"📋 Description: {description}")
        print("-" * 50)

        print("🔍 Analyzing requirements and generating app...")
        async for message in query(prompt=prompt, options=options):
            if hasattr(message, "content") and message.content:
                # Show progress updates
                content = str(message.content)
                if len(content) > 100:
                    print(f"📝 {content[:100]}...")
                else:
                    print(f"📝 {content}")

        # Check if app was created
        app_path = Path(f"examples/{app_name}.py")
        if app_path.exists():
            print(f"✅ App created successfully at {app_path}")
            return True
        else:
            print(f"❌ App file not found at {app_path}")
            return False

    except ImportError:
        print(
            "❌ Claude Code SDK not available. Install with: pip install claude-code-sdk"
        )
        return False
    except Exception as e:
        print(f"❌ Error creating app: {e}")
        return False


def main():
    """Main function"""
    # Check if running inside Claude Code
    if detect_claude_code_environment():
        show_usage_instructions()
        return

    # Parse command line arguments
    if len(sys.argv) < 3:
        print("Usage: python standalone_app_creator.py '<description>' '<app_name>'")
        print(
            "Example: python standalone_app_creator.py 'Survey about favorite colors' 'color_survey'"
        )
        sys.exit(1)

    description = sys.argv[1]
    app_name = sys.argv[2]

    # Sanitize app name
    app_name = "".join(c for c in app_name if c.isalnum() or c in "_-").lower()

    # Create the app
    try:
        success = asyncio.run(create_app_with_sdk(description, app_name))
        if success:
            print(f"🎉 Success! Your app '{app_name}' is ready to use.")
        else:
            print(f"❌ Failed to create app '{app_name}'.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
