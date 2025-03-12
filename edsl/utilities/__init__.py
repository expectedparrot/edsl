"""
Utility functions and classes for the EDSL package.

This module provides various utility functions and classes used across the EDSL package.
"""

# Core classes
from .pretty_list import PrettyList
from .template_loader import TemplateLoader

# String utilities
from .string_utils import (
    random_string,
    is_valid_variable_name,
    create_valid_var_name,
    shorten_string,
    sanitize_string,
    text_to_shortname,
)

# JSON utilities
from .json_utils import (
    dict_hash,
    clean_json,
    repair_json,
    extract_json_from_string,
    merge_dicts,
)

# File utilities
from .file_utils import (
    is_gzipped,
    hash_value,
    file_notice,
    HTMLSnippet,
)

# Display utilities
from .display_utils import (
    Markdown,
    dict_to_html,
)

# Decorator utilities
from .decorator_utils import (
    time_it,
    time_all_functions,
    add_edsl_version,
    jupyter_nb_handler,
    sync_wrapper,
)
from .decorators import add_edsl_version
from .remove_edsl_version import remove_edsl_version

# Notebook utilities
from .is_notebook import is_notebook

# Validation utilities
from .validation_utils import (
    is_valid_variable_name,
    extract_variable_names,
)

# Converter utilities
from .converter_utils import (
    MarkdownToDocx,
    MarkdownToPDF,
)

# Restricted Python
from .restricted_python import create_restricted_function