"""
EDSL package main entry point with dynamic method discovery.

This module provides the main entry point when the EDSL package is executed directly
using `python -m edsl`.
"""

import sys
import typer
import inspect
import json
import cmd
from pathlib import Path
from typing import Optional, Any, Dict, List, Tuple
from rich.console import Console
from rich.table import Table
import os
import shlex
import warnings
import ast
import readline
import re
import types

warnings.filterwarnings("ignore", category=UserWarning, module="edsl\.scenarios\.file_store")

# Path for persistent CLI history
HISTORY_FILE = Path.home() / ".edsl_cli_commands_log"

# Create the main Typer app
app = typer.Typer(help="EDSL - Expected Parrot Domain Specific Language", invoke_without_command=True)
console = Console()

# Currently focused object (top of stack)
_loaded_object = None
_loaded_object_name = None

# Maintain a stack of all objects that have been loaded/created in the session.
# The first element in each tuple is a human-readable name for the object, the
# second element is the object itself.  Indexing is 1-based when shown to the
# user so that $1 refers to the first entry, $2 the second and so on.
_object_stack: List[Tuple[str, Any]] = []

# Shell command names that should never be overridden by dynamically added
# methods from loaded objects. This prevents conflicts like `load` which the
# shell uses for switching focus.
_RESERVED_SHELL_COMMANDS = {
    "load",
    "stack",
    "info",
    "methods",
    "exit",
    "quit",
    "EOF",
    "ls",
    "cd",
    "unload",
    "pull",
    "agent",
    "scenario",
}

# Built-in functions to expose as additional CLI/shell commands
_BUILTIN_FUNCTIONS = {
    "len": len,
    "str": str,
    "repr": repr,
    "hash": hash,
    "dir": dir,
    "type": lambda obj: type(obj).__name__,  # Return the object's type name
    "id": id,
    "print": lambda obj: str(obj),  # Alias to show the object's string representation
}

# ---------------------------------------------------------------------------
# Stack reference resolver
# ---------------------------------------------------------------------------


def _resolve_stack_reference(token: str):
    """If token matches $<n>, return corresponding object from stack, else return token."""
    if isinstance(token, str) and re.fullmatch(r"\$\d+", token):
        idx = int(token[1:]) - 1
        if 0 <= idx < len(_object_stack):
            return _object_stack[idx][1]
    return token


# ---------------------------------------------------------------------------
# Helper to parse positional/keyword args from a line (needs to be before class)
# ---------------------------------------------------------------------------


def _parse_line_args_kwargs(line: str):
    """Parse a command line string into (args, kwargs)."""
    # Use posix=False so we retain quotes inside tokens (important for dict strings)
    tokens = shlex.split(line, posix=False)
    positional = []
    keyword = {}
    for tok in tokens:
        tok = tok.strip()
        if "=" in tok:
            key, val = tok.split("=", 1)
            # Try literal_eval first (handles dicts/lists/numbers/strings)
            resolved_val = _resolve_stack_reference(val)
            if resolved_val is not val:
                val_eval = resolved_val
            else:
                try:
                    val_eval = ast.literal_eval(val)
                except Exception:
                    # Fallback: strip quotes
                    if (val.startswith("'") and val.endswith("'")) or (
                        val.startswith('"') and val.endswith('"')
                    ):
                        val_eval = val[1:-1]
                    else:
                        val_eval = val
            keyword[key] = val_eval
        else:
            resolved = _resolve_stack_reference(tok)
            if resolved is tok:
                # try literal eval for positional
                try:
                    resolved = ast.literal_eval(tok)
                except Exception:
                    pass
            positional.append(resolved)
    return positional, keyword


class EDSLShell(cmd.Cmd):
    """Interactive shell for loaded EDSL objects."""
    
    def __init__(self, loaded_object: Any = None, object_name: Optional[str] = None):
        super().__init__()
        # Load persistent history if available
        try:
            if HISTORY_FILE.exists():
                readline.read_history_file(str(HISTORY_FILE))
        except Exception:
            pass
        self.loaded_object = loaded_object
        self.object_name = object_name if object_name else "None"
        if self.loaded_object is None:
            self.intro = "\nInteractive EDSL Shell (no object loaded)"
            self.prompt = "edsl> "
        else:
            self.intro = f"\nInteractive EDSL Shell - {self.object_name} loaded"
            self.prompt = f"edsl ({self.object_name})> "
        
        # Add dynamic methods to the shell
        self._add_dynamic_methods()
    
    def _add_dynamic_methods(self):
        """Add methods from the loaded object as shell commands."""
        # If no object is loaded, nothing to add (other than built-ins if desired)
        if self.loaded_object is None:
            return

        methods = _get_callable_methods(self.loaded_object)
        
        for method_name, method in methods.items():
            # Create a wrapper function for the method
            def make_wrapper(method_name, method):
                def wrapper(line):
                    return self._call_method(method_name, line)
                return wrapper
            
            # Skip reserved command names to avoid clobbering built-ins like 'load'.
            if method_name in _RESERVED_SHELL_COMMANDS:
                continue
            
            # Add the method to the shell
            setattr(self, f'do_{method_name}', make_wrapper(method_name, method))
            
            # Add help for the method
            help_text = method.__doc__ or f"Call {method_name} method on loaded {self.object_name}"
            setattr(self, f'help_{method_name}', lambda: console.print(help_text))
        
        # ---------------------------------------------------------------
        # Add built-in function wrappers (len, str, repr, etc.)
        # ---------------------------------------------------------------

        for func_name, func in _BUILTIN_FUNCTIONS.items():
            # Avoid overriding reserved or existing commands
            if func_name in _RESERVED_SHELL_COMMANDS or hasattr(self, f'do_{func_name}'):
                continue

            def make_builtin_wrapper(func_name, func):
                def wrapper(line):
                    try:
                        console.print(f"[cyan]Calling built-in {func_name}({self.object_name})...[/cyan]")
                        result = func(self.loaded_object)
                        if result is not None:
                            console.print(f"[green]Result:[/green] {result}")
                    except Exception as e:
                        console.print(f"[red]Error calling built-in {func_name}: {e}[/red]")
                return wrapper

            setattr(self, f'do_{func_name}', make_builtin_wrapper(func_name, func))
            setattr(self, f'help_{func_name}', lambda: console.print(f"Apply Python built-in '{func_name}' to the loaded object."))
    
    def _call_method(self, method_name, line):
        """Call a method on the loaded object."""
        if self.loaded_object is None:
            console.print("[yellow]No object loaded. Use 'load <FILEPATH>' first.[/yellow]")
            return
        try:
            method = getattr(self.loaded_object, method_name)

            tokens = shlex.split(line)
            positional_args = []
            keyword_args = {}

            for tok in tokens:
                if "=" in tok:
                    key, val = tok.split("=", 1)
                    # Strip surrounding quotes if any
                    if (val.startswith("'") and val.endswith("'")) or (
                        val.startswith('"') and val.endswith('"')
                    ):
                        val = val[1:-1]
                    # Try to safely evaluate literal (e.g., numbers, True, False)
                    try:
                        val_eval = ast.literal_eval(val)
                    except Exception:
                        val_eval = val
                    keyword_args[key] = val_eval
                else:
                    positional_args.append(tok)

            preview_args = [str(a) for a in positional_args] + [f"{k}={v}" for k, v in keyword_args.items()]
            console.print(
                f"[cyan]Calling {self.object_name}.{method_name}({', '.join(preview_args)})...[/cyan]"
            )

            result = method(*positional_args, **keyword_args)
            
            # Display result
            if result is not None:
                console.print(f"[green]Result:[/green]")
                if isinstance(result, (dict, list)):
                    console.print_json(json.dumps(result, indent=2, default=str))
                else:
                    console.print(str(result))

                # Push new objects onto the stack automatically
                # Primitive return types (str, int, etc.) shouldn't be added.
                if not isinstance(result, (str, int, float, bool, bytes, bytearray)):
                    new_name = result.__class__.__name__
                    _add_to_stack(new_name, result)
                    console.print(
                        f"[cyan]Added new object to stack as ${len(_object_stack)} ({new_name}). Switched focus.[/cyan]"
                    )

                    # Update shell context
                    self.loaded_object = result
                    self.object_name = new_name
                    self.prompt = f"edsl ({new_name})> "

                    # Refresh dynamic methods for the new object
                    self._add_dynamic_methods()

                    # Register new dynamic commands for the freshly focused object (CLI)
                    _register_dynamic_commands()
            else:
                console.print("[green]✓ Method executed successfully[/green]")
                
        except Exception as e:
            console.print(f"[red]Error calling {method_name}: {e}[/red]")
    
    def do_info(self, line):
        """Show information about the loaded object."""
        console.print(f"[cyan]Loaded object: {self.object_name}[/cyan]")
        
        # Show object properties
        table = Table(title="Object Properties")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        # Get non-callable attributes
        for name in dir(self.loaded_object):
            if not name.startswith('_') and not callable(getattr(self.loaded_object, name)):
                value = getattr(self.loaded_object, name)
                # Truncate long values
                str_value = str(value)
                if len(str_value) > 100:
                    str_value = str_value[:97] + "..."
                table.add_row(name, str_value)
        
        console.print(table)
    
    def do_methods(self, line):
        """List all available methods on the loaded object."""
        methods = _get_callable_methods(self.loaded_object)
        
        table = Table(title=f"Methods for {self.object_name}")
        table.add_column("Method", style="cyan")
        table.add_column("Signature", style="yellow")
        table.add_column("Description", style="white")
        
        for method_name, method in methods.items():
            if method_name in _RESERVED_SHELL_COMMANDS:
                continue
            try:
                sig = inspect.signature(method)
            except (TypeError, ValueError):
                sig = None
            doc = method.__doc__ or "No description available"
            first_line = doc.split('\n')[0].strip()
            table.add_row(method_name, str(sig) if sig else "No signature", first_line)
        
        console.print(table)
    
    def do_exit(self, line):
        """Exit the interactive shell."""
        try:
            readline.write_history_file(str(HISTORY_FILE))
        except Exception:
            pass
        console.print("[yellow]Goodbye![/yellow]")
        return True
    
    def do_quit(self, line):
        """Exit the interactive shell."""
        return self.do_exit(line)
    
    def do_EOF(self, line):
        """Handle Ctrl+D to exit."""
        try:
            readline.write_history_file(str(HISTORY_FILE))
        except Exception:
            pass
        console.print("")
        return self.do_exit(line)
    
    def emptyline(self):
        """Handle empty line input."""
        pass
    
    def default(self, line):
        """Handle unknown commands."""
        attr_name = line.strip().split()[0]
        if hasattr(self.loaded_object, attr_name):
            value = getattr(self.loaded_object, attr_name)
            import inspect
            if inspect.isroutine(value):
                console.print(f"[red]Unknown command or callable requires parentheses: {attr_name}[/red]")
            else:
                console.print(f"[green]Attribute {attr_name}:[/green] {value}")

                # Push non-primitive objects to stack
                if not isinstance(value, (str, int, float, bool, bytes, bytearray)):
                    new_name = value.__class__.__name__
                    _add_to_stack(new_name, value)
                    console.print(
                        f"[cyan]Added attribute value to stack as ${len(_object_stack)} ({new_name}).[/cyan]"
                    )
                    # Update focus
                    self.loaded_object = value
                    self.object_name = new_name
                    self.prompt = f"edsl ({new_name})> "
                    self._add_dynamic_methods()
                    _register_dynamic_commands()
            return

        console.print(f"[red]Unknown command: {line}[/red]")
        console.print("[yellow]Type 'methods' to see available methods or 'help' for help.[/yellow]")

    def do_stack(self, line):
        """Show the current object stack."""
        _print_stack()

    def do_load(self, line):
        """Load a file or switch to an object in the stack.

        Usage examples:
          load /path/to/file.json
          load $3            # Focus the object at position 3 in the stack
        """

        target = line.strip()
        if not target:
            console.print("[yellow]Usage: load <filepath>|$<n>[/yellow]")
            return

        # Handle stack reference ($n)
        if target.startswith("$"):
            try:
                idx = int(target[1:]) - 1
                if idx < 0 or idx >= len(_object_stack):
                    raise IndexError
                name, obj = _object_stack[idx]

                # Switch focus
                self.loaded_object = obj
                self.object_name = name

                # Update globals too
                global _loaded_object, _loaded_object_name
                _loaded_object = obj
                _loaded_object_name = name

                self.prompt = f"edsl ({name})> "
                # Refresh dynamic methods for newly focused object
                self._add_dynamic_methods()
                console.print(f"[green]Switched focus to {name} (${idx+1})[/green]")
            except (ValueError, IndexError):
                console.print("[red]Invalid stack reference.[/red]")
            return

        # Otherwise treat as filepath
        try:
            load(Path(target), object_type="auto", interactive=False)

            # Bring shell context in sync with global state
            self.loaded_object = _loaded_object
            self.object_name = _loaded_object_name
            self.prompt = f"edsl ({self.object_name})> "
            # Refresh dynamic methods after loading new object
            self._add_dynamic_methods()
        except Exception:
            # Errors are already printed in load(); simply pass
            pass

    def do_unload(self, line):
        """Unload the current object and clear the stack."""
        _unload()
        # Update shell prompt/context
        self.loaded_object = None
        self.object_name = None
        self.prompt = "edsl> "

    # -------------------------------------------------------------------
    # Filesystem operations
    # -------------------------------------------------------------------

    def do_ls(self, line):
        """List directory contents. Usage: ls [path] [--all|-a]"""
        tokens = shlex.split(line)
        show_hidden = False
        path = Path.cwd()
        for token in tokens:
            if token in ("-a", "--all"):
                show_hidden = True
            else:
                path = Path(token).expanduser()
        _print_directory(path, show_hidden)

    def do_cd(self, line):
        """Change current directory. Usage: cd <path>"""
        target = line.strip() or "~"
        path = Path(target).expanduser()
        if not path.exists() or not path.is_dir():
            console.print(f"[red]Directory '{path}' does not exist.[/red]")
            return
        try:
            os.chdir(path)
            console.print(f"[green]✓ Changed directory to {path}[/green]")
        except Exception as e:
            console.print(f"[red]Error changing directory: {e}[/red]")

    # -------------------------------------------------------------------
    # Coop pull operation
    # -------------------------------------------------------------------

    def do_pull(self, line):
        """Pull an object from Expected Parrot Coop by UUID.

        Usage: pull <uuid>
        """

        uuid_str = line.strip()
        if not uuid_str:
            console.print("[yellow]Usage: pull <uuid>[/yellow]")
            return

        try:
            from edsl.coop import Coop

            console.print(f"[cyan]Pulling object {uuid_str} from Coop...[/cyan]")
            coop = Coop()
            obj = coop.pull(uuid_str)

            new_name = obj.__class__.__name__
            _add_to_stack(new_name, obj)

            # Update shell context
            self.loaded_object = obj
            self.object_name = new_name
            self.prompt = f"edsl ({new_name})> "

            # Refresh dynamic methods
            self._add_dynamic_methods()

            # Register CLI dynamic commands
            _register_dynamic_commands()

            console.print(f"[green]✓ Pulled object {uuid_str} as {new_name} (${len(_object_stack)})[/green]")
        except Exception as e:
            # Attempt Jobs-specific pull fallback
            try:
                from edsl.coop import Coop
                from edsl.jobs import Jobs  # type: ignore
                coop = Coop()
                job_data = coop.new_remote_inference_get(str(uuid_str), include_json_string=True)
                import json as _json
                job_dict = _json.loads(job_data.get("job_json_string"))
                obj = Jobs.from_dict(job_dict)

                new_name = obj.__class__.__name__
                _add_to_stack(new_name, obj)

                self.loaded_object = obj
                self.object_name = new_name
                self.prompt = f"edsl ({new_name})> "
                self._add_dynamic_methods()
                _register_dynamic_commands()

                console.print(f"[green]✓ Pulled Jobs object {uuid_str} as {new_name} (${len(_object_stack)})[/green]")
            except Exception as e2:
                console.print(f"[red]Error pulling object: {e} | Fallback failed: {e2}[/red]")

    # -------------------------------------------------------------------
    # Instantiate new objects: agent / scenario
    # -------------------------------------------------------------------

    def do_agent(self, line):
        """Instantiate an Agent object.

        Usage: agent [args] [key=value ...]
        """
        try:
            from edsl.agents import Agent
        except ImportError as e:
            console.print(f"[red]Could not import Agent: {e}[/red]")
            return

        args, kwargs = _parse_line_args_kwargs(line)

        # Avoid duplicate dict positional arg when traits passed via keyword
        if args and isinstance(args[0], dict) and 'traits' in kwargs:
            args = args[1:]

        try:
            obj = Agent(*args, **kwargs)
            new_name = obj.__class__.__name__
            _add_to_stack(new_name, obj)

            # Switch focus
            self.loaded_object = obj
            self.object_name = new_name
            self.prompt = f"edsl ({new_name})> "
            self._add_dynamic_methods()
            _register_dynamic_commands()

            console.print(f"[green]✓ Created {new_name} (${len(_object_stack)})[/green]")
        except Exception as e:
            console.print(f"[red]Error creating Agent: {e}[/red]")

    def do_scenario(self, line):
        """Instantiate a Scenario object.

        Usage: scenario [args] [key=value ...]
        """
        try:
            from edsl.scenarios import Scenario
        except ImportError as e:
            console.print(f"[red]Could not import Scenario: {e}[/red]")
            return

        args, kwargs = _parse_line_args_kwargs(line)

        # Avoid duplicate dict positional arg when traits passed via keyword
        if args and isinstance(args[0], dict) and 'traits' in kwargs:
            args = args[1:]

        try:
            obj = Scenario(*args, **kwargs)
            new_name = obj.__class__.__name__
            _add_to_stack(new_name, obj)

            # Switch focus
            self.loaded_object = obj
            self.object_name = new_name
            self.prompt = f"edsl ({new_name})> "
            self._add_dynamic_methods()
            _register_dynamic_commands()

            console.print(f"[green]✓ Created {new_name} (${len(_object_stack)})[/green]")
        except Exception as e:
            console.print(f"[red]Error creating Scenario: {e}[/red]")


def _get_callable_methods(obj: Any) -> Dict[str, callable]:
    """Get all callable methods from an object that don't start with underscore."""
    methods: Dict[str, callable] = {}
    for name in dir(obj):
        if name.startswith('_'):
            continue
        attr = getattr(obj, name)
        # Only expose if it is a proper function/method/descriptor routine, not just any callable object
        if inspect.isfunction(attr) or inspect.ismethod(attr) or isinstance(attr, (types.MethodType, types.FunctionType, types.BuiltinFunctionType, types.BuiltinMethodType, types.MethodDescriptorType)):
            methods[name] = attr
    return methods


def _create_dynamic_command(method_name: str, method: callable):
    """Create a dynamic typer command for a method."""
    
    def dynamic_command(*args, **kwargs):
        """Dynamically created command."""
        if _loaded_object is None:
            console.print("[red]Error: No object loaded. Use 'edsl load FILEPATH' first.[/red]")
            raise typer.Exit(1)
        
        try:
            # Get the method from the loaded object
            method = getattr(_loaded_object, method_name)
            
            # Call the method
            console.print(f"[cyan]Calling {_loaded_object_name}.{method_name}()...[/cyan]")
            result = method(*args, **kwargs)
            
            # Display result
            if result is not None:
                console.print(f"[green]Result:[/green]")
                if isinstance(result, (dict, list)):
                    console.print_json(json.dumps(result, indent=2, default=str))
                else:
                    console.print(str(result))

                # Push new objects onto the stack automatically
                # Primitive return types (str, int, etc.) shouldn't be added.
                if not isinstance(result, (str, int, float, bool, bytes, bytearray)):
                    new_name = result.__class__.__name__
                    _add_to_stack(new_name, result)
                    console.print(
                        f"[cyan]Added new object to stack as ${len(_object_stack)} ({new_name}).[/cyan]"
                    )
                    # Register new dynamic commands for the freshly focused object
                    _register_dynamic_commands()
            else:
                console.print("[green]✓ Method executed successfully[/green]")
                
        except Exception as e:
            console.print(f"[red]Error calling {method_name}: {e}[/red]")
            raise typer.Exit(1)
    
    # Get method signature for help
    try:
        sig = inspect.signature(method)
    except (TypeError, ValueError):
        sig = None
    docstring = method.__doc__ or f"Call {method_name} method on loaded object"
    
    # Set the command name and help
    dynamic_command.__name__ = method_name
    dynamic_command.__doc__ = docstring if sig is not None else f"{docstring} (no signature)"
    
    return dynamic_command


def _create_builtin_cli_command(func_name: str, func):
    """Create a Typer command that applies a built-in function to the loaded object."""

    def builtin_command():
        if _loaded_object is None:
            console.print("[red]Error: No object loaded. Use 'edsl load FILEPATH' first.[/red]")
            raise typer.Exit(1)

        try:
            console.print(f"[cyan]Calling built-in {func_name}({_loaded_object_name})...[/cyan]")
            result = func(_loaded_object)

            # Display result
            if result is not None:
                console.print(f"[green]Result:[/green] {result}")
        except Exception as e:
            console.print(f"[red]Error calling built-in {func_name}: {e}[/red]")
            raise typer.Exit(1)

    builtin_command.__name__ = func_name
    builtin_command.__doc__ = f"Apply Python built-in '{func_name}' to the currently loaded object."

    return builtin_command


def _register_dynamic_commands():
    """Register dynamic commands based on the loaded object's methods."""
    global _loaded_object
    
    if _loaded_object is None:
        return
    
    methods = _get_callable_methods(_loaded_object)
    
    for method_name, method in methods.items():
        # Skip if command already exists
        if method_name in _RESERVED_SHELL_COMMANDS or hasattr(app, method_name):
            continue
            
        # Create and register the dynamic command
        dynamic_cmd = _create_dynamic_command(method_name, method)
        app.command(name=method_name, help=f"Call {method_name} on loaded {_loaded_object_name}")(dynamic_cmd)

    # -------------------------------------------------------------------
    # Register built-in function commands (len, str, etc.)
    # -------------------------------------------------------------------

    for func_name, func in _BUILTIN_FUNCTIONS.items():
        # Avoid clobbering existing commands or reserved words
        if func_name in _RESERVED_SHELL_COMMANDS or hasattr(app, func_name):
            continue

        builtin_cmd = _create_builtin_cli_command(func_name, func)
        app.command(name=func_name, help=f"Apply built-in '{func_name}' to loaded {_loaded_object_name}")(builtin_cmd)


@app.command()
def load(
    filepath: Path = typer.Argument(..., help="Path to the file to load"),
    object_type: Optional[str] = typer.Option(
        "auto", "--type", "-t", help="Object type to load (auto, filestore, scenario, etc.)"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Start interactive shell after loading"
    ),
) -> None:
    """
    Load a file as an EDSL object and make its methods available as CLI commands.
    
    After loading, you can either:
    1. Call methods directly: python -m edsl <method_name> [args]
    2. Start interactive shell: python -m edsl load FILEPATH --interactive
    3. Start shell after loading: python -m edsl shell
    
    Args:
        filepath: Path to the file to load
        object_type: Type of object to create (auto-detected by default)
        interactive: Start interactive shell after loading
    """
    global _loaded_object, _loaded_object_name
    
    # Check if file exists
    if not filepath.exists():
        console.print(f"[red]Error: File '{filepath}' does not exist[/red]")
        raise typer.Exit(1)
    
    if not filepath.is_file():
        console.print(f"[red]Error: '{filepath}' is not a file[/red]")
        raise typer.Exit(1)
    
    try:
        # Import FileStore from scenarios
        from .scenarios.file_store import FileStore
        
        console.print(f"[cyan]Loading '{filepath}' as EDSL object...[/cyan]")
        
        # Create the appropriate object based on type
        if object_type == "auto":
            try:
                from edsl.utilities.edsl_load import load as edsl_generic_load

                temp_obj = edsl_generic_load(str(filepath))
                temp_name = temp_obj.__class__.__name__

                _add_to_stack(temp_name, temp_obj)
            except Exception as e:
                console.print(
                    f"[yellow]Auto load failed with '{e}'. Falling back to FileStore.[/yellow]"
                )
                # Fallback to FileStore
                temp_obj = FileStore(str(filepath))
                temp_name = "FileStore"
                _add_to_stack(temp_name, temp_obj)
        elif object_type == "filestore":
            temp_obj = FileStore(str(filepath))
            temp_name = "FileStore"

            # Add to stack and set as current
            _add_to_stack(temp_name, temp_obj)
        else:
            console.print(f"[red]Error: Unknown object type '{object_type}'[/red]")
            raise typer.Exit(1)
        
        console.print(f"[green]✓ Successfully loaded {_loaded_object_name}[/green]")
        console.print(f"[cyan]File: {filepath}[/cyan]")
        
        if interactive:
            console.print(f"\n[yellow]Starting interactive shell...[/yellow]")
            shell = EDSLShell(_loaded_object, _loaded_object_name)
            shell.cmdloop()
        else:
            _register_dynamic_commands()
        
    except ImportError as e:
        console.print(f"[red]Error: Failed to import required modules. {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading file: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def info():
    """Show information about the currently loaded object."""
    if _loaded_object is None:
        console.print("[red]No object loaded. Use 'edsl load FILEPATH' first.[/red]")
        raise typer.Exit(1)
    
    console.print(f"[cyan]Loaded object: {_loaded_object_name}[/cyan]")
    
    # Show object properties
    table = Table(title="Object Properties")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    
    # Get non-callable attributes
    for name in dir(_loaded_object):
        if not name.startswith('_') and not callable(getattr(_loaded_object, name)):
            value = getattr(_loaded_object, name)
            # Truncate long values
            str_value = str(value)
            if len(str_value) > 100:
                str_value = str_value[:97] + "..."
            table.add_row(name, str_value)
    
    console.print(table)


@app.command()
def methods():
    """List all available methods on the loaded object."""
    if _loaded_object is None:
        console.print("[red]No object loaded. Use 'edsl load FILEPATH' first.[/red]")
        raise typer.Exit(1)
    
    methods = _get_callable_methods(_loaded_object)
    
    table = Table(title=f"Methods for {_loaded_object_name}")
    table.add_column("Method", style="cyan")
    table.add_column("Signature", style="yellow")
    table.add_column("Description", style="white")
    
    for method_name, method in methods.items():
        if method_name in _RESERVED_SHELL_COMMANDS:
            continue
        try:
            sig = inspect.signature(method)
        except (TypeError, ValueError):
            sig = None
        doc = method.__doc__ or "No description available"
        first_line = doc.split('\n')[0].strip()
        table.add_row(method_name, str(sig) if sig else "No signature", first_line)
    
    console.print(table)


@app.command()
def shell():
    """Start an interactive shell for the loaded object."""
    if _loaded_object is None:
        console.print("[red]No object loaded. Use 'edsl load FILEPATH' first.[/red]")
        raise typer.Exit(1)
    
    console.print(f"[yellow]Starting interactive shell for {_loaded_object_name}...[/yellow]")
    shell = EDSLShell(_loaded_object, _loaded_object_name)
    shell.cmdloop()


@app.command()
def version():
    """Show the EDSL version."""
    try:
        from importlib import metadata
        version = metadata.version("edsl")
        console.print(f"[bold cyan]EDSL version:[/bold cyan] {version}")
    except metadata.PackageNotFoundError:
        console.print(
            "[yellow]EDSL package not installed or version not available.[/yellow]"
        )


@app.command()
def stack():
    """Show the current object stack."""
    _print_stack()


@app.command()
def unload():
    """Unload the current object and clear the stack."""
    _unload()


@app.command(name="ls", help="List files in a directory")
def ls_cli(
    path: Path = typer.Argument(None, help="Path to list (defaults to current directory)"),
    all: bool = typer.Option(False, "--all", "-a", help="Include hidden files"),
):
    _print_directory(path if path else Path.cwd(), show_hidden=all)


@app.command(name="cd", help="Change current working directory")
def cd_cli(path: Path = typer.Argument("~", help="Directory to change to")):
    path = path.expanduser()
    if not path.exists() or not path.is_dir():
        console.print(f"[red]Directory '{path}' does not exist.[/red]")
        raise typer.Exit(1)
    try:
        os.chdir(path)
        console.print(f"[green]✓ Changed directory to {path}[/green]")
    except Exception as e:
        console.print(f"[red]Error changing directory: {e}")
        raise typer.Exit(1)


@app.command(name="pull", help="Pull an object from Expected Parrot Coop by UUID")
def pull_cli(uuid: str = typer.Argument(..., help="UUID of the object to pull")):
    """Pull an object from Coop, add to stack, and register commands."""
    try:
        from edsl.coop import Coop

        coop = Coop()
        obj = coop.pull(uuid)

        new_name = obj.__class__.__name__
        _add_to_stack(new_name, obj)

        console.print(f"[green]✓ Pulled object {uuid} as {new_name} (${len(_object_stack)})[/green]")

        # Register dynamic commands for the new object
        _register_dynamic_commands()
    except Exception as e:
        # Attempt Jobs-specific pull fallback
        try:
            from edsl.coop import Coop
            from edsl.jobs import Jobs  # type: ignore
            coop = Coop()
            job_data = coop.new_remote_inference_get(str(uuid), include_json_string=True)
            import json as _json
            job_dict = _json.loads(job_data.get("job_json_string"))
            obj = Jobs.from_dict(job_dict)

            new_name = obj.__class__.__name__
            _add_to_stack(new_name, obj)

            self.loaded_object = obj
            self.object_name = new_name
            self.prompt = f"edsl ({new_name})> "
            self._add_dynamic_methods()
            _register_dynamic_commands()

            console.print(f"[green]✓ Pulled Jobs object {uuid} as {new_name} (${len(_object_stack)})[/green]")
        except Exception as e2:
            console.print(f"[red]Error pulling object: {e} | Fallback failed: {e2}[/red]")


@app.callback()
def callback(
    ctx: typer.Context,
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Start interactive shell without loading an object."
    ),
):
    """
    EDSL - Expected Parrot Survey Language
    
    A toolkit for creating, managing, and running surveys with language models.
    
    If invoked without any command, prints helpful usage information instead of an error.
    """

    # Handle --interactive with no subcommand
    if interactive and ctx.invoked_subcommand is None:
        console.print("[yellow]Starting interactive shell (no object loaded)...[/yellow]")
        shell = EDSLShell()
        shell.cmdloop()
        raise typer.Exit()

    # If no subcommand was supplied, give a gentle hint instead of an error.
    if ctx.invoked_subcommand is None:
        if _loaded_object is None:
            console.print(
                "[yellow]No object loaded. Use 'edsl load <FILEPATH>' to get started or 'edsl --help' for more options.[/yellow]"
            )
        else:
            console.print(
                f"[cyan]{_loaded_object_name} is currently loaded. Use 'edsl methods' to list available actions.[/cyan]"
            )
        # Exit cleanly without error
        raise typer.Exit()


def _add_to_stack(name: str, obj: Any) -> None:
    """Append the object to the global stack and make it the current object."""
    global _loaded_object, _loaded_object_name

    _object_stack.append((name, obj))
    _loaded_object = obj
    _loaded_object_name = name


def _unload() -> None:
    """Reset session to an empty state (no object loaded, empty stack)."""
    global _loaded_object, _loaded_object_name, _object_stack

    if _loaded_object is None:
        console.print("[yellow]No object is currently loaded.[/yellow]")
        return

    _loaded_object = None
    _loaded_object_name = None
    # Do NOT clear the stack; keep past objects for reference

    console.print("[green]✓ Unloaded current object.[/green]")


def _print_stack() -> None:
    """Pretty-print the current object stack."""
    if not _object_stack:
        console.print("[yellow]Stack is empty.[/yellow]")
        return

    table = Table(title="Object Stack")
    table.add_column("#", style="cyan")
    table.add_column("Object", style="white")

    for idx, (name, obj) in enumerate(_object_stack, start=1):
        current_marker = " (current)" if obj is _loaded_object else ""
        table.add_row(f"${idx}", f"{name}{current_marker}")

    console.print(table)


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _print_directory(path: Path, show_hidden: bool = False) -> None:
    """Pretty-print the contents of a directory using a Rich table."""
    if not path.exists() or not path.is_dir():
        console.print(f"[red]'{path}' is not a valid directory.[/red]")
        return

    entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    table = Table(title=f"Contents of {path}")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Size", style="white", justify="right")

    for entry in entries:
        if not show_hidden and entry.name.startswith('.'):
            continue
        entry_type = "Dir" if entry.is_dir() else "File"
        size = "-" if entry.is_dir() else f"{entry.stat().st_size} B"
        table.add_row(entry.name, entry_type, size)

    console.print(table)


def main():
    """Main entry point for the EDSL package when executed as a module."""
    app()


if __name__ == "__main__":
    main()