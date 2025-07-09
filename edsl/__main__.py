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
import shutil
from functools import lru_cache
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

warnings.filterwarnings("ignore", category=UserWarning, module="edsl\.scenarios\.file_store")

# Path for persistent CLI history
HISTORY_FILE = Path.home() / ".edsl_cli_commands_log"

# Active env profile
_active_profile: Optional[str] = None

# Create the main Typer app
app = typer.Typer(help="EDSL - Expected Parrot Domain Specific Language (use .help for dot commands)", invoke_without_command=True)
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
    "create",
    "show_key",
    "switch",
    "profiles",
    "pop",
    "clear",
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


# ---------------------------------------------------------------------------
# Stdin handling for piped data
# ---------------------------------------------------------------------------


def _load_from_stdin() -> bool:
    """
    Check if there's data on stdin and try to load it as an EDSL object.
    Returns True if an object was successfully loaded, False otherwise.
    """
    # Only try to read from stdin if it's not connected to a terminal (i.e., piped data)
    if sys.stdin.isatty():
        return False
    
    try:
        # Read all data from stdin
        stdin_data = sys.stdin.read().strip()
        if not stdin_data:
            return False
        
        console.print("[cyan]Reading EDSL object from stdin...[/cyan]")
        
        # After reading piped data, restore stdin to terminal for interactive use
        _restore_stdin_to_terminal()
        
        # Try to parse as JSON first
        try:
            data = json.loads(stdin_data)
        except json.JSONDecodeError:
            console.print("[red]Error: Stdin data is not valid JSON[/red]")
            return False
        
        # Try to use EDSL's generic load functionality
        try:
            from edsl.base.base_class import RegisterSubclassesMeta
            
            # If the data is a dict with EDSL object structure, try to load it
            if isinstance(data, dict) and "edsl_class_name" in data:
                class_name = data["edsl_class_name"]
                registry = RegisterSubclassesMeta.get_registry()
                
                if class_name not in registry:
                    console.print(f"[red]Unknown EDSL class '{class_name}'. Available: {', '.join(registry.keys())}[/red]")
                    return False
                
                cls = registry[class_name]
                obj = cls.from_dict(data)
                new_name = obj.__class__.__name__
                _add_to_stack(new_name, obj)
                console.print(f"[green]✓ Successfully loaded {new_name} from stdin (${len(_object_stack)})[/green]")
                _register_dynamic_commands()
                return True
            else:
                console.print("[yellow]Stdin data doesn't appear to be a serialized EDSL object (missing 'edsl_class_name')[/yellow]")
                return False
                
        except ImportError:
            console.print("[yellow]Warning: Could not import EDSL registry utilities[/yellow]")
            return False
        except Exception as e:
            # If generic load fails, try other approaches
            console.print(f"[yellow]Generic load failed: {e}[/yellow]")
            
            # Try to instantiate based on class name if present
            if isinstance(data, dict) and "edsl_class_name" in data:
                try:
                    class_name = data["edsl_class_name"]
                    # Remove metadata fields
                    obj_data = {k: v for k, v in data.items() if not k.startswith("edsl_")}
                    
                    obj = _instantiate_from_registry(class_name, [], obj_data)
                    new_name = obj.__class__.__name__
                    _add_to_stack(new_name, obj)
                    console.print(f"[green]✓ Successfully created {new_name} from stdin data (${len(_object_stack)})[/green]")
                    _register_dynamic_commands()
                    return True
                except Exception as e2:
                    console.print(f"[red]Failed to instantiate object from stdin data: {e2}[/red]")
                    return False
            else:
                console.print("[red]Unable to determine object type from stdin data[/red]")
                return False
                
    except Exception as e:
        console.print(f"[red]Error reading from stdin: {e}[/red]")
        return False


def _restore_stdin_to_terminal():
    """Restore stdin to be connected to the terminal for interactive input."""
    try:
        # Close current stdin and reopen it to the terminal
        sys.stdin.close()
        sys.stdin = open('/dev/tty', 'r')
    except Exception:
        # If we can't restore to /dev/tty, try to at least reset stdin
        try:
            import io
            sys.stdin = io.TextIOWrapper(io.BufferedReader(io.FileIO(0)))
        except Exception:
            # Last resort: just continue with current stdin
            pass


# ---------------------------------------------------------------------------
# Registry instantiation helper (must appear before shell usage)
# ---------------------------------------------------------------------------


@lru_cache()
def _get_registry():
    from edsl.coop.utils import ObjectRegistry
    return ObjectRegistry.get_registry()


def _instantiate_from_registry(class_name: str, args: list, kwargs: dict):
    """Instantiate object using registry with catch-all parameter mapping."""
    registry = _get_registry()
    cls = registry.get(class_name) or registry.get(class_name.capitalize()) or registry.get(class_name.lower())
    if cls is None:
        raise ValueError(f"Unknown class '{class_name}'. Available: {', '.join(registry.keys())}")

    sig = inspect.signature(cls.__init__)
    formal_params = {
        p.name for p in sig.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY) and p.name != 'self'
    }
    var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

    preferred = ['traits', 'data', 'attributes', 'params']
    catch = next((n for n in preferred if n in formal_params), None)

    extra = {k: kwargs.pop(k) for k in list(kwargs.keys()) if k not in formal_params}
    if extra:
        if catch:
            if catch in kwargs and isinstance(kwargs[catch], dict):
                kwargs[catch].update(extra)
            else:
                kwargs[catch] = extra
        elif var_kw:
            kwargs.update(extra)
        else:
            raise TypeError(f"Unknown parameters: {', '.join(extra.keys())}")

    if catch and args and isinstance(args[0], dict) and catch not in kwargs:
        kwargs[catch] = args.pop(0)

    return cls(*args, **kwargs)


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
                            console.print(f"[green]Returned:[/green] {result}")
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
                console.print(f"[green]Returned:[/green]")
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
        command = line.strip()
        
        # Handle dot commands (SQLite-style)
        if command.startswith('.'):
            parts = command.split(None, 1)
            dot_command = parts[0][1:]  # Remove the leading dot
            dot_args = parts[1] if len(parts) > 1 else ""
            
            # Map dot commands to their corresponding methods
            dot_command_map = {
                'load': self.do_dot_load,
                'stack': self.do_dot_stack,
                'unload': self.do_dot_unload,
                'pull': self.do_dot_pull,
                'create': self.do_dot_create,
                'show_key': self.do_dot_show_key,
                'profiles': self.do_dot_profiles,
                'switch': self.do_dot_switch,
                'pop': self.do_dot_pop,
                'clear': self.do_dot_clear,
                'help': self.do_dot_help,
                'quit': self.do_quit,
                'exit': self.do_exit,
            }
            
            if dot_command in dot_command_map:
                return dot_command_map[dot_command](dot_args)
            else:
                console.print(f"[red]Unknown dot command: .{dot_command}[/red]")
                console.print("[yellow]Available dot commands: .load, .stack, .unload, .pull, .create, .show_key, .profiles, .switch, .pop, .clear, .help, .quit, .exit[/yellow]")
                return
        
        # Handle regular attribute access
        attr_name = command.split()[0]
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

        console.print(f"[red]Unknown command: {command}[/red]")
        console.print("[yellow]Type 'methods' to see available methods or '.help' for help.[/yellow]")

    # -------------------------------------------------------------------
    # Dot command implementations (SQLite-style)
    # -------------------------------------------------------------------

    def do_dot_load(self, line):
        """Load a file or switch to an object in the stack."""
        target = line.strip()
        if not target:
            console.print("[yellow]Usage: .load <filepath>|$<n>[/yellow]")
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

    def do_dot_stack(self, line):
        """Show the current object stack."""
        _print_stack()

    def do_dot_unload(self, line):
        """Unload the current object and clear the stack."""
        _unload()
        # Update shell prompt/context
        self.loaded_object = None
        self.object_name = None
        self.prompt = "edsl> "

    def do_dot_pull(self, line):
        """Pull an object from Expected Parrot Coop by UUID."""
        uuid_str = line.strip()
        if not uuid_str:
            console.print("[yellow]Usage: .pull <uuid>[/yellow]")
            return

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

    def do_dot_create(self, line):
        """Create an object from the registry."""
        if not line.strip():
            console.print("[yellow]Usage: .create <ClassName> [args] [key=value ...][/yellow]")
            return

        # Split only first token for class name
        parts = line.strip().split(maxsplit=1)
        class_name = parts[0]
        arg_line = parts[1] if len(parts) > 1 else ""

        # If arg_line starts with dict/list literal keep as single positional
        if arg_line.lstrip().startswith(('{', '[')):
            try:
                arg_obj = ast.literal_eval(arg_line.strip())
                args = [arg_obj]
                kwargs = {}
            except Exception as e:
                console.print(f"[red]Failed to parse literal: {e}[/red]")
                raise typer.Exit(1)
        else:
            args, kwargs = _parse_line_args_kwargs(arg_line)

        try:
            obj = _instantiate_from_registry(class_name, args, kwargs)
            new_name = obj.__class__.__name__
            _add_to_stack(new_name, obj)
            # Switch focus
            self.loaded_object = obj
            self.object_name = new_name
            self.prompt = f"edsl ({new_name})> "
            self._add_dynamic_methods()
            _register_dynamic_commands()

            console.print(f"[green]✓ Created {new_name} (${len(_object_stack)})[/green]")
        except Exception as err:
            console.print(f"[red]Error creating object: {err}[/red]")
            raise typer.Exit(1)

    def do_dot_show_key(self, line):
        """Display the current Expected Parrot API key (masked)."""
        key = _get_expected_parrot_key()
        if key:
            masked = key[:4] + "..." + key[-4:]
            console.print(f"[green]Expected Parrot key:[/green] {masked}")
        else:
            console.print("[yellow]No Expected Parrot key found in environment.[/yellow]")

    def do_dot_profiles(self, line):
        """List available .env_<profile> files."""
        profiles = _list_env_profiles()
        if profiles:
            console.print("[cyan]Available profiles:[/cyan]")
            for p in profiles:
                name = p[len('.env_'):]
                console.print(f" • {name} ({p})")
        else:
            console.print("[yellow]No profiles found.[/yellow]")

    def do_dot_switch(self, line):
        """Switch to a given environment profile."""
        profile = line.strip()
        if not profile:
            console.print("[yellow]Usage: .switch <profile>[/yellow]")
            return
        ok = _load_env_profile(profile)
        if ok:
            console.print(f"[green]✓ Switched to profile '{profile}' and reloaded .env[/green]")
        else:
            console.print(f"[red]Profile '.env_{profile}' not found.[/red]")

    def do_dot_pop(self, line):
        """Remove the currently focused object from the stack and switch to the previous one."""
        if not _object_stack:
            console.print("[yellow]Stack is empty - nothing to pop.[/yellow]")
            return

        if self.loaded_object is None:
            console.print("[yellow]No object is currently focused.[/yellow]")
            return

        # Find the current object in the stack
        current_idx = None
        for idx, (name, obj) in enumerate(_object_stack):
            if obj is self.loaded_object:
                current_idx = idx
                break

        if current_idx is None:
            console.print("[yellow]Current object not found in stack.[/yellow]")
            return

        # Remove the current object from the stack
        removed_name, removed_obj = _object_stack.pop(current_idx)
        console.print(f"[green]✓ Popped {removed_name} from stack[/green]")

        # Update global state
        global _loaded_object, _loaded_object_name

        # If stack is now empty, unload everything
        if not _object_stack:
            _loaded_object = None
            _loaded_object_name = None
            self.loaded_object = None
            self.object_name = None
            self.prompt = "edsl> "
            console.print("[yellow]Stack is now empty - no object loaded.[/yellow]")
        else:
            # Switch to the previous object in the stack
            if current_idx >= len(_object_stack):
                # We removed the last item, focus on the new last item
                new_idx = len(_object_stack) - 1
            else:
                # We removed a middle item, focus on the item that took its place
                # But let's actually focus on the previous item if it exists
                new_idx = max(0, current_idx - 1)

            new_name, new_obj = _object_stack[new_idx]
            
            # Update global and local state
            _loaded_object = new_obj
            _loaded_object_name = new_name
            self.loaded_object = new_obj
            self.object_name = new_name
            self.prompt = f"edsl ({new_name})> "
            
            # Refresh dynamic methods for the new object
            self._add_dynamic_methods()
            _register_dynamic_commands()
            
            console.print(f"[green]Switched focus to {new_name} (${new_idx+1})[/green]")

    def do_dot_clear(self, line):
        """Clear the entire object stack but keep current focus."""
        if not _object_stack:
            console.print("[yellow]Stack is already empty.[/yellow]")
            return

        # Count objects before clearing
        count = len(_object_stack)
        current_obj = self.loaded_object
        current_name = self.object_name

        # Clear the stack
        _object_stack.clear()

        # If we had a focused object, add it back as the only item
        if current_obj is not None and current_name is not None:
            _object_stack.append((current_name, current_obj))
            console.print(f"[green]✓ Cleared {count} objects from stack, kept current focus on {current_name}[/green]")
        else:
            console.print(f"[green]✓ Cleared {count} objects from stack[/green]")

        # Update global state to match
        global _loaded_object, _loaded_object_name
        if current_obj is not None:
            _loaded_object = current_obj
            _loaded_object_name = current_name
        else:
            _loaded_object = None
            _loaded_object_name = None


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


    # -------------------------------------------------------------------
    # Instantiate new objects: agent / scenario
    # -------------------------------------------------------------------


    # -------------------------------------------------------------------
    # Show Expected Parrot key
    # -------------------------------------------------------------------


    # -------------------------------------------------------------------
    # Profile management
    # -------------------------------------------------------------------


    def do_dot_help(self, line):
        """Show comprehensive help for EDSL commands."""
        
        help_table = Table(title="EDSL Commands", show_header=True, header_style="bold cyan")
        help_table.add_column("Command", style="cyan", width=15)
        help_table.add_column("Description", style="white", width=50)
        help_table.add_column("Example", style="yellow", width=30)
        
        commands_help = [
            (".load", "Load a file or switch focus", ".load myfile.json or .load $2"),
            (".create", "Create an object from registry", ".create Agent"),
            (".pull", "Pull object from Coop by UUID", ".pull abc-123-def"),
            (".info", "Show info about loaded object", ".info"),
            (".methods", "List available methods", ".methods"),
            (".stack", "Show object stack", ".stack"),
            (".unload", "Unload current object", ".unload"),
            (".pop", "Remove current from stack", ".pop"),
            (".clear", "Clear stack but keep focus", ".clear"),
            ("ls", "List directory contents", "ls /path"),
            ("cd", "Change directory", "cd /path"),
            (".profiles", "List env profiles", ".profiles"),
            (".switch", "Switch env profile", ".switch dev"),
            (".show_key", "Show API key (masked)", ".show_key"),
            ("exit/quit", "Exit the shell", "exit"),
            (".help", "Show this help", ".help"),
        ]
        
        for cmd, desc, example in commands_help:
            help_table.add_row(cmd, desc, example)
        
        console.print(help_table)
        
        console.print("\n[bold cyan]Method Calls:[/bold cyan]")
        console.print("  Call any method on the loaded object directly:")
        console.print("  method_name arg1 arg2 key=value")
        console.print("  Example: run")
        console.print("  Example: to_dict")
        
        console.print("\n[bold cyan]Built-in Functions:[/bold cyan]")
        console.print("  len, str, repr, hash, dir, type, id, print")
        console.print("  Example: len  # calls len() on loaded object")
        
        console.print("\n[bold cyan]Stack References:[/bold cyan]")
        console.print("  Use $1, $2, $3, etc. to reference objects in the stack")
        console.print("  Example: .load $2  # switch focus to object #2")



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
            console.print("[red]Error: No object loaded. Use 'edsl .load FILEPATH' first.[/red]")
            raise typer.Exit(1)
        
        try:
            # Get the method from the loaded object
            method = getattr(_loaded_object, method_name)
            
            # Call the method
            console.print(f"[cyan]Calling {_loaded_object_name}.{method_name}()...[/cyan]")
            result = method(*args, **kwargs)
            
            # Display result
            if result is not None:
                console.print(f"[green]Returned:[/green]")
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
            console.print("[red]Error: No object loaded. Use 'edsl .load FILEPATH' first.[/red]")
            raise typer.Exit(1)

        try:
            console.print(f"[cyan]Calling built-in {func_name}({_loaded_object_name})...[/cyan]")
            result = func(_loaded_object)

            # Display result
            if result is not None:
                console.print(f"[green]Returned:[/green] {result}")
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


@app.command(name=".load")
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
    2. Start interactive shell: python -m edsl .load FILEPATH --interactive
    3. Start shell after loading: python -m edsl .shell
    
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


@app.command(name=".info")
def info():
    """Show information about the currently loaded object."""
    if _loaded_object is None:
        console.print("[red]No object loaded. Use 'edsl .load FILEPATH' first.[/red]")
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


@app.command(name=".methods")
def methods():
    """List all available methods on the loaded object."""
    if _loaded_object is None:
        console.print("[red]No object loaded. Use 'edsl .load FILEPATH' first.[/red]")
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


@app.command(name=".shell")
def shell():
    """Start an interactive shell for the loaded object."""
    if _loaded_object is None:
        console.print("[red]No object loaded. Use 'edsl .load FILEPATH' first.[/red]")
        raise typer.Exit(1)
    
    console.print(f"[yellow]Starting interactive shell for {_loaded_object_name}...[/yellow]")
    shell = EDSLShell(_loaded_object, _loaded_object_name)
    shell.cmdloop()


@app.command(name=".version")
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


@app.command(name=".stack")
def stack():
    """Show the current object stack."""
    _print_stack()


@app.command(name=".unload")
def unload():
    """Unload the current object and clear the stack."""
    _unload()


@app.command(name=".ls", help="List files in a directory")
def ls_cli(
    path: Path = typer.Argument(None, help="Path to list (defaults to current directory)"),
    all: bool = typer.Option(False, "--all", "-a", help="Include hidden files"),
):
    _print_directory(path if path else Path.cwd(), show_hidden=all)


@app.command(name=".cd", help="Change current working directory")
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


@app.command(name=".pull", help="Pull an object from Expected Parrot Coop by UUID")
def pull_cli(uuid: str = typer.Argument(..., help="UUID of the object to pull")):
    """Pull an object from Coop, add to stack, and register commands."""
    from edsl.coop import Coop

    coop = Coop()
    obj = coop.pull(uuid)

    new_name = obj.__class__.__name__
    _add_to_stack(new_name, obj)

    console.print(f"[green]✓ Pulled object {uuid} as {new_name} (${len(_object_stack)})[/green]")

    # Register dynamic commands for the new object
    _register_dynamic_commands()


@app.command(name=".test-stdin", help="Output a test EDSL object for testing stdin functionality")
def test_stdin():
    """Create and output a simple EDSL object for testing stdin functionality.
    
    Usage example:
        python -m edsl test-stdin | python -m edsl
    """
    try:
        from edsl.agents import Agent
        
        # Create a simple agent
        agent = Agent(traits={"persona": "A helpful test agent"})
        
        # Output the serialized object
        import json
        output = json.dumps(agent.to_dict(), indent=2, default=str)
        print(output)
        
    except ImportError as e:
        console.print(f"[red]Error: Could not import required modules. {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error creating test object: {e}[/red]")
        raise typer.Exit(1)


@app.callback()
def callback(
    ctx: typer.Context,
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Force interactive mode (interactive is now the default when no command is given)."
    ),
):
    """
    EDSL - Expected Parrot Survey Language
    
    A toolkit for creating, managing, and running surveys with language models.
    
    All commands use dot prefixes (e.g., .load, .create, .pull).
    Use .help to see all available commands.
    
    EDSL supports reading serialized objects from stdin when used in a pipeline.
    For example: echo '{"edsl_class_name": "Agent", ...}' | python -m edsl
    Or: python -m edsl .test-stdin | python -m edsl
    
    If invoked without any command, starts an interactive shell.
    """

    # Check for and process stdin data first
    stdin_loaded = False
    if not sys.stdin.isatty():
        stdin_loaded = _load_from_stdin()

    # If no subcommand was supplied, default to interactive mode
    if ctx.invoked_subcommand is None:
        if stdin_loaded:
            console.print(f"[yellow]Starting interactive shell with loaded {_loaded_object_name}...[/yellow]")
            shell = EDSLShell(_loaded_object, _loaded_object_name)
        else:
            console.print("[yellow]Starting interactive shell (no object loaded)...[/yellow]")
            shell = EDSLShell()
        shell.cmdloop()
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


def _get_expected_parrot_key():
    """Return Expected Parrot key from env or .env search."""
    key_names = ("EXPECTED_PARROT_API_KEY", "EXPECTED_PARROT_KEY", "EP_KEY")
    for k in key_names:
        val = os.getenv(k)
        if val:
            return val

    # If python-dotenv isn't available, do a simple manual parse for cwd .env
    if not load_dotenv:
        current_env = Path.cwd() / ".env"
        if current_env.exists():
            try:
                with current_env.open() as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")  # strip surrounding quotes if any
                            if k in key_names:
                                return v
            except Exception:
                pass
    return None


def _load_env_profile(profile: str) -> bool:
    """Switch to a profile by copying .env_<profile> to .env and backing up the old .env."""
    global _active_profile

    filename = f".env_{profile}"
    profile_path = None
    
    # Find the profile file
    for p in [Path.cwd()] + list(Path.cwd().parents):
        candidate = p / filename
        if candidate.exists():
            profile_path = candidate
            break

    if profile_path is None:
        home_candidate = Path.home() / filename
        if home_candidate.exists():
            profile_path = home_candidate

    if profile_path is None:
        return False

    # Work in the current directory for .env management
    current_dir = Path.cwd()
    env_path = current_dir / ".env"
    env_bak_path = current_dir / ".env_bak"

    try:
        # Step 1: Backup current .env to .env_bak if it exists
        if env_path.exists():
            console.print(f"[cyan]Backing up current .env to .env_bak...[/cyan]")
            shutil.copy2(env_path, env_bak_path)

        # Step 2: Copy the profile to .env
        console.print(f"[cyan]Copying {profile_path} to .env...[/cyan]")
        shutil.copy2(profile_path, env_path)

        # Step 3: Clear existing environment variables first
        for var in ("EXPECTED_PARROT_API_KEY", "EXPECTED_PARROT_KEY", "EP_KEY"):
            os.environ.pop(var, None)

        # Step 4: Reload the new .env file
        if load_dotenv:
            load_dotenv(env_path, override=True)
        else:
            # Fallback manual parsing when python-dotenv is not installed
            with env_path.open() as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")  # strip surrounding quotes if any
                    os.environ[k] = v

        _active_profile = profile
        return True

    except Exception as e:
        console.print(f"[red]Error switching profile: {e}[/red]")
        return False


def _list_env_profiles() -> List[str]:
    """Return list of .env_<profile> filenames discovered."""
    seen: set[str] = set()
    paths = [Path.cwd()] + list(Path.cwd().parents) + [Path.home()]
    for p in paths:
        for env_file in p.glob(".env_*"):
            seen.add(env_file.name)
    return sorted(seen)


# -------------------------------------------------------------------
# Additional CLI commands
# -------------------------------------------------------------------


@app.command(name=".profiles", help="List available environment profiles")
def profiles_cli():
    profiles = _list_env_profiles()
    if profiles:
        console.print("[cyan]Available profiles:[/cyan]")
        for p in profiles:
            name = p[len('.env_'):]
            console.print(f" • {name} ({p})")
    else:
        console.print("No profiles found.")


@app.command(name=".switch", help="Switch to environment profile (backs up .env to .env_bak and copies profile to .env)")
def switch_cli(profile: str = typer.Argument(..., help="Profile name")):
    if _load_env_profile(profile):
        console.print(f"[green]✓ Switched to profile '{profile}' and reloaded .env[/green]")
    else:
        console.print(f"[red]Profile '.env_{profile}' not found.[/red]")
        raise typer.Exit(1)


@app.command(name=".create", help="Create an object from the registry")
def create_cli(
    class_name: str = typer.Argument(..., help="Class name to instantiate"),
    args: Optional[str] = typer.Argument(None, help="Arguments for the class (as string)")
):
    """Create an object from the registry."""
    
    if not args:
        args = ""
    
    # If args starts with dict/list literal keep as single positional
    if args.lstrip().startswith(('{', '[')):
        try:
            arg_obj = ast.literal_eval(args.strip())
            positional_args = [arg_obj]
            keyword_args = {}
        except Exception as e:
            console.print(f"[red]Failed to parse literal: {e}[/red]")
            raise typer.Exit(1)
    else:
        positional_args, keyword_args = _parse_line_args_kwargs(args)

    try:
        obj = _instantiate_from_registry(class_name, positional_args, keyword_args)
        new_name = obj.__class__.__name__
        _add_to_stack(new_name, obj)
        _register_dynamic_commands()

        console.print(f"[green]✓ Created {new_name} (${len(_object_stack)})[/green]")
    except Exception as err:
        console.print(f"[red]Error creating object: {err}[/red]")
        raise typer.Exit(1)


@app.command(name=".show_key", help="Display the current Expected Parrot API key (masked)")
def show_key_cli():
    """Display the current Expected Parrot API key (masked)."""
    key = _get_expected_parrot_key()
    if key:
        masked = key[:4] + "..." + key[-4:]
        console.print(f"[green]Expected Parrot key:[/green] {masked}")
    else:
        console.print("[yellow]No Expected Parrot key found in environment.[/yellow]")


@app.command(name=".pop", help="Remove the currently focused object from the stack")
def pop_cli():
    """Remove the currently focused object from the stack and switch to the previous one."""
    global _loaded_object, _loaded_object_name
    
    if not _object_stack:
        console.print("[yellow]Stack is empty - nothing to pop.[/yellow]")
        return

    if _loaded_object is None:
        console.print("[yellow]No object is currently focused.[/yellow]")
        return

    # Find the current object in the stack
    current_idx = None
    for idx, (name, obj) in enumerate(_object_stack):
        if obj is _loaded_object:
            current_idx = idx
            break

    if current_idx is None:
        console.print("[yellow]Current object not found in stack.[/yellow]")
        return

    # Remove the current object from the stack
    removed_name, removed_obj = _object_stack.pop(current_idx)
    console.print(f"[green]✓ Popped {removed_name} from stack[/green]")

    # If stack is now empty, unload everything
    if not _object_stack:
        _loaded_object = None
        _loaded_object_name = None
        console.print("[yellow]Stack is now empty - no object loaded.[/yellow]")
    else:
        # Switch to the previous object in the stack
        if current_idx >= len(_object_stack):
            # We removed the last item, focus on the new last item
            new_idx = len(_object_stack) - 1
        else:
            # We removed a middle item, focus on the item that took its place
            # But let's actually focus on the previous item if it exists
            new_idx = max(0, current_idx - 1)

        new_name, new_obj = _object_stack[new_idx]
        
        # Update global state
        _loaded_object = new_obj
        _loaded_object_name = new_name
        
        _register_dynamic_commands()
        
        console.print(f"[green]Switched focus to {new_name} (${new_idx+1})[/green]")


@app.command(name=".clear", help="Clear the entire object stack but keep current focus")
def clear_cli():
    """Clear the entire object stack but keep current focus."""
    global _loaded_object, _loaded_object_name
    
    if not _object_stack:
        console.print("[yellow]Stack is already empty.[/yellow]")
        return

    # Count objects before clearing
    count = len(_object_stack)
    current_obj = _loaded_object
    current_name = _loaded_object_name

    # Clear the stack
    _object_stack.clear()

    # If we had a focused object, add it back as the only item
    if current_obj is not None and current_name is not None:
        _object_stack.append((current_name, current_obj))
        console.print(f"[green]✓ Cleared {count} objects from stack, kept current focus on {current_name}[/green]")
        _loaded_object = current_obj
        _loaded_object_name = current_name
    else:
        console.print(f"[green]✓ Cleared {count} objects from stack[/green]")
        _loaded_object = None
        _loaded_object_name = None


@app.command(name=".help", help="Show help for EDSL commands")
def help_cli():
    """Show comprehensive help for EDSL dot commands."""
    
    help_table = Table(title="EDSL Dot Commands", show_header=True, header_style="bold cyan")
    help_table.add_column("Command", style="cyan", width=15)
    help_table.add_column("Description", style="white", width=50)
    help_table.add_column("Example", style="yellow", width=30)
    
    commands_help = [
        (".load", "Load a file as an EDSL object", ".load myfile.json"),
        (".create", "Create an object from registry", ".create Agent"),
        (".pull", "Pull object from Coop by UUID", ".pull abc-123-def"),
        (".info", "Show info about loaded object", ".info"),
        (".methods", "List available methods", ".methods"),
        (".stack", "Show object stack", ".stack"),
        (".unload", "Unload current object", ".unload"),
        (".pop", "Remove current from stack", ".pop"),
        (".clear", "Clear stack but keep focus", ".clear"),
        (".shell", "Start interactive shell", ".shell"),
        (".ls", "List directory contents", ".ls /path"),
        (".cd", "Change directory", ".cd /path"),
        (".profiles", "List env profiles", ".profiles"),
        (".switch", "Switch env profile", ".switch dev"),
        (".show_key", "Show API key (masked)", ".show_key"),
        (".version", "Show EDSL version", ".version"),
        (".test-stdin", "Output test object", ".test-stdin"),
        (".help", "Show this help", ".help"),
    ]
    
    for cmd, desc, example in commands_help:
        help_table.add_row(cmd, desc, example)
    
    console.print(help_table)
    
    console.print("\n[bold cyan]Usage Examples:[/bold cyan]")
    console.print("  python -m edsl .load myfile.json")
    console.print("  python -m edsl .create Agent traits='{\"persona\": \"helpful\"}'")
    console.print("  python -m edsl .shell  # Start interactive mode")
    console.print("  python -m edsl  # Start interactive mode (default)")
    
    console.print("\n[bold cyan]Interactive Shell:[/bold cyan]")
    console.print("  Once in the shell, you can use dot commands or call methods directly")
    console.print("  Example: .load myfile.json")
    console.print("  Example: run  # calls the run() method on loaded object")
    
    console.print("\n[bold cyan]Stack References:[/bold cyan]")
    console.print("  Use $1, $2, $3, etc. to reference objects in the stack")
    console.print("  Example: .load $2  # switch focus to object #2")


def main():
    """Main entry point for the EDSL package when executed as a module."""
    # If no arguments provided, start interactive shell directly
    if len(sys.argv) == 1:
        # Check for stdin data even when no arguments provided
        stdin_loaded = False
        if not sys.stdin.isatty():
            stdin_loaded = _load_from_stdin()
        
        if stdin_loaded:
            console.print(f"[yellow]Starting interactive shell with loaded {_loaded_object_name}...[/yellow]")
            shell = EDSLShell(_loaded_object, _loaded_object_name)
        else:
            console.print("[yellow]Starting interactive shell (no object loaded)...[/yellow]")
            shell = EDSLShell()
        shell.cmdloop()
    else:
        app()


if __name__ == "__main__":
    main()