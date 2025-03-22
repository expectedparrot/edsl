# Core utilities - used across the codebase
from .template_loader import TemplateLoader
from .PrettyList import PrettyList
from .restricted_python import create_restricted_function
from .remove_edsl_version import remove_edsl_version
from .ast_utilities import extract_variable_names

# Functions from utilities.py
from .utilities import (
    clean_json,
    dict_hash,
    hash_value,
    repair_json,
    create_valid_var_name,
    random_string,
    shorten_string,
    is_gzipped
)

# Decorator utilities
from .decorators import sync_wrapper, jupyter_nb_handler

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
    "sync_wrapper",
    "jupyter_nb_handler",
    "is_notebook",
    "is_valid_variable_name",
    "sanitize_string"
]

