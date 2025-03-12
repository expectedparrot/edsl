"""
Legacy module for backward compatibility.
"""

from .string_utils import (
    random_string,
    shorten_string,
    create_valid_var_name,
    text_to_shortname,
)

from .json_utils import (
    clean_json,
    dict_hash,
    repair_json,
    extract_json_from_string,
    merge_dicts,
    fix_partial_correct_response,
)

from .file_utils import (
    is_gzipped,
    hash_value,
    file_notice,
    HTMLSnippet,
)

from .display_utils import (
    dict_to_html,
)

from .notebook_utils import (
    is_notebook,
)

from .validation_utils import (
    is_valid_variable_name,
)