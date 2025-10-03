#!/usr/bin/env python3
"""
Claude EDSL App Creator

Uses the Claude Code SDK to automatically generate EDSL apps based on descriptions.
The script analyzes the app description, references existing patterns and the development guide,
creates the app, and tests it with iterative fixes.
"""

import asyncio
import os
import sys
import traceback
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

# Claude Code SDK imports
try:
    from claude_code_sdk import ClaudeSDKClient, ClaudeCodeOptions
    from claude_code_sdk import CLINotFoundError, CLIConnectionError, ProcessError
    SDK_AVAILABLE = True
except ImportError as e:
    print(f"Error importing Claude Code SDK: {e}")
    print("Run: pip install claude-code-sdk")
    SDK_AVAILABLE = False


class EDSLAppCreator:
    """Creates EDSL apps using Claude Code SDK"""

    def __init__(self):
        self.examples_dir = Path(__file__).parent
        self.guide_path = self.examples_dir / "EDSL_App_Development_Guide.md"

        # Configure Claude agent with necessary tools
        self.agent_options = ClaudeCodeOptions(
            system_prompt=self._get_system_prompt(),
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            permission_mode="acceptEdits",  # Auto-accept file edits
            max_turns=50,  # Limit turns to avoid infinite loops
            continue_conversation=False  # Don't continue existing conversation
        )

    def _get_system_prompt(self) -> str:
        """Generate system prompt with EDSL context"""
        return """You are an expert EDSL app developer. Your task is to create high-quality EDSL applications based on descriptions.

Key responsibilities:
1. Analyze the app description to understand requirements
2. Reference existing EDSL patterns from the development guide and examples
3. Generate complete, working EDSL apps following established patterns
4. Test the apps and fix any issues iteratively
5. Ensure code follows EDSL conventions and best practices

You have access to:
- EDSL App Development Guide at examples/EDSL_App_Development_Guide.md
- Multiple example apps in the examples directory
- The full EDSL codebase for reference

When creating apps:
- Follow the 4-component pattern: initial_survey, jobs_object, output_formatters, App instance
- Use appropriate question types from edsl.questions
- Implement proper error handling and validation
- Include meaningful example usage
- Make apps self-contained and reusable

Focus on creating production-ready code that follows EDSL conventions."""

    async def create_app(self, description: str, app_name: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Create an EDSL app based on description

        Args:
            description: Natural language description of the desired app
            app_name: Name for the app file (without .py extension)
            output_path: Optional custom output path

        Returns:
            Dictionary with creation results
        """
        try:
            # Import query function here to avoid issues if SDK not available
            from claude_code_sdk import query

            if output_path is None:
                output_path = self.examples_dir / f"{app_name}.py"

            # Create a comprehensive prompt that does everything in one go
            full_prompt = f"""
I need you to create a complete, working EDSL app. Here's what I need:

## App Requirements:
**Description**: {description}
**App Name**: {app_name}
**Output Path**: {output_path}

## Your Tasks:
1. **Analyze Requirements**: Read the EDSL App Development Guide at examples/EDSL_App_Development_Guide.md to understand patterns
2. **Study Examples**: Look at 2-3 relevant existing example apps in the examples directory for reference patterns
3. **Create the App**: Generate a complete, working EDSL app following these steps:
   - Identify the appropriate app type (General Purpose, Ranking, TrueSkill, or Persona Generation)
   - Create proper initial survey with appropriate question types
   - Design the jobs pipeline logic
   - Implement output formatters
   - Include proper imports from edsl.app, edsl.surveys, edsl.questions, etc.
   - Add a test example in the if __name__ == "__main__": block
   - Include clear docstrings

4. **Test and Fix**: Run the app to ensure it works, fixing any import or runtime issues

## Key Requirements:
- The app should handle AgentList as input along with generation instructions
- Use AgentList directly with questions to generate responses
- Return original scenario list augmented with generated content
- Follow established EDSL patterns and conventions
- Make it production-ready and self-contained

Please complete all these steps and create a working app at {output_path}.
"""

            print(f"🚀 Creating EDSL app: {app_name}")
            print("🔍 Analyzing patterns, generating code, and testing...")

            messages = []
            async for message in query(prompt=full_prompt, options=self.agent_options):
                messages.append(message)
                # Print some feedback about what's happening
                if hasattr(message, 'content') and message.content:
                    content_preview = str(message.content)[:100]
                    print(f"📝 {content_preview}..." if len(str(message.content)) > 100 else f"📝 {content_preview}")

            # Check if file was actually created
            if not Path(output_path).exists():
                return {
                    "status": "error",
                    "error": f"App file was not created at {output_path}. The Claude session may not have executed the Write commands.",
                    "messages_received": len(messages)
                }

            return {
                "status": "success",
                "app_name": app_name,
                "output_path": str(output_path),
                "description": description,
                "messages_received": len(messages)
            }

        except CLINotFoundError:
            return {
                "status": "error",
                "error": "Claude Code CLI not found. Please install Claude Code first."
            }
        except CLIConnectionError as e:
            return {
                "status": "error",
                "error": f"Connection error: {e}"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Unexpected error: {e}\n{traceback.format_exc()}"
            }

    async def interactive_mode(self):
        """Interactive mode for creating multiple apps"""
        print("🤖 Claude EDSL App Creator - Interactive Mode")
        print("=" * 50)

        while True:
            print("\nOptions:")
            print("1. Create new app")
            print("2. Exit")

            choice = input("Choose option (1-2): ").strip()

            if choice == "2":
                print("Goodbye! 👋")
                break
            elif choice == "1":
                description = input("\n📝 Describe the app you want to create: ").strip()
                if not description:
                    print("❌ Description cannot be empty")
                    continue

                app_name = input("📁 Enter app name (without .py): ").strip()
                if not app_name:
                    print("❌ App name cannot be empty")
                    continue

                # Sanitize app name
                app_name = "".join(c for c in app_name if c.isalnum() or c in "_-").lower()

                print(f"\n🚀 Creating app: {app_name}")
                print(f"📋 Description: {description}")
                print("-" * 40)

                result = await self.create_app(description, app_name)

                if result["status"] == "success":
                    print(f"✅ App created successfully!")
                    print(f"📄 File: {result['output_path']}")
                else:
                    print(f"❌ Error creating app: {result['error']}")
            else:
                print("❌ Invalid choice")


def _detect_claude_code_session():
    """Detect if we're already running inside a Claude Code session"""
    # Check for environment variables that Claude Code might set
    claude_indicators = [
        'CLAUDE_CODE_SESSION',
        'CLAUDE_CLI_SESSION',
        'ANTHROPIC_CLI_SESSION'
    ]

    for indicator in claude_indicators:
        if os.getenv(indicator):
            return True

    # Check if we can detect Claude Code processes
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'claude' in proc.info['name'].lower():
                    return True
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline']).lower()
                    if 'claude-code' in cmdline or 'claude code' in cmdline:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except ImportError:
        pass

    return False

async def main():
    """Main function"""
    if not SDK_AVAILABLE:
        print("❌ Claude Code SDK is not available. Please install it with: pip install claude-code-sdk")
        sys.exit(1)

    # Check if we're in a Claude Code session
    if _detect_claude_code_session():
        print("⚠️  Warning: Detected that we may be running inside Claude Code already.")
        print("🔄 The Claude Code SDK cannot spawn new sessions from within an existing session.")
        print("💡 To use this app creator:")
        print("   1. Exit this Claude Code session")
        print("   2. Run the script from a regular terminal")
        print("   3. Or ask Claude directly in this session to create your app")
        sys.exit(1)

    creator = EDSLAppCreator()

    if len(sys.argv) > 1:
        # Command line mode
        if len(sys.argv) < 3:
            print("Usage: python claude_edsl_app_creator.py '<description>' '<app_name>' [output_path]")
            print("Example: python claude_edsl_app_creator.py 'Create a survey for restaurant feedback' 'restaurant_feedback'")
            sys.exit(1)

        description = sys.argv[1]
        app_name = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else None

        print(f"🚀 Creating EDSL app: {app_name}")
        print(f"📋 Description: {description}")
        print("-" * 50)

        result = await creator.create_app(description, app_name, output_path)

        if result["status"] == "success":
            print(f"✅ App created successfully!")
            print(f"📄 File: {result['output_path']}")
        else:
            print(f"❌ Error: {result['error']}")
            sys.exit(1)
    else:
        # Interactive mode
        await creator.interactive_mode()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)