# Core utilities - used across the codebase
from .template_loader import TemplateLoader
from .PrettyList import PrettyList
from .restricted_python import create_restricted_function
from .remove_edsl_version import remove_edsl_version
from .ast_utilities import extract_variable_names
from .local_results_cache import object_disk_cache
from .edsl_load import load as edsl_load

# from .show_diff import show_diff  # Not used in this module

# Functions from utilities.py
from .utilities import (
    clean_json,
    dict_hash,
    hash_value,
    repair_json,
    create_valid_var_name,
    random_string,
    shorten_string,
    is_gzipped,
    sanitize_jinja_syntax,
)

# Decorator utilities
from .decorators import sync_wrapper, jupyter_nb_handler, memory_profile

# Spinner utilities
from .spinner import with_spinner, silent_spinner

# Standalone utilities
from .is_notebook import is_notebook
from .is_valid_variable_name import is_valid_variable_name
from .naming_utilities import sanitize_string

# Interface module - note: print_results_long is imported directly in results.py

__all__ = [
    "TemplateLoader",
    "PrettyList",
    "create_restricted_function",
    "remove_edsl_version",
    "extract_variable_names",
    "clean_json",
    "dict_hash",
    "hash_value",
    "repair_json",
    "create_valid_var_name",
    "random_string",
    "shorten_string",
    "is_gzipped",
    "sanitize_jinja_syntax",
    "sync_wrapper",
    "jupyter_nb_handler",
    "memory_profile",
    "with_spinner",
    "silent_spinner",
    "is_notebook",
    "is_valid_variable_name",
    "sanitize_string",
    "object_disk_cache",
    "edsl_load",
]
