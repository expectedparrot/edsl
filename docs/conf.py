# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import sys
import os

import sphinx
import inspect
from sphinx.application import Sphinx

project = "edsl"
copyright = "2024 Expected Parrot, Inc."
author = "Expected Parrot, Inc."

print("Current working directory:")
print(os.getcwd())

print("System path:")
print(sys.path)


sys.path.insert(0, os.path.abspath("../"))
print("System path after insert:")
print(sys.path)


username = "expectedparrot"
projectname = "edsl"


def linkcode_resolve(domain, info):
    if domain != "py":
        return None
    if not info["module"]:
        return None
    filename = info["module"].replace(".", "/")
    return f"https://github.com/{username}/{projectname}/blob/main/{filename}.py"


# def linkcode_resolve(domain, info):
#     if domain != 'py':
#         return None
#     if not info['module']:
#         return None

#     module_name = info['module']
#     full_name = info['fullname']

#     obj = sphinx.ext.linkcode.import_object(module_name, full_name)
#     if obj is None:
#         return None

#     try:
#         file = inspect.getsourcefile(obj)
#         _, lineno = inspect.getsourcelines(obj)
#     except Exception:
#         file = None
#         lineno = None

#     if file and lineno:
#         rel_file = os.path.relpath(file, start=os.path.dirname(yourpackage.__file__))
#         filename = rel_file.replace(os.path.sep, '/')
#         return f"https://github.com/{username}/{projectname}/blob/main/{filename}#L{lineno}"

#     filename = module_name.replace('.', '/')
#     return f"https://github.com/{username}/{projectname}/blob/main/{filename}.py"


def print_directory_tree(startpath):
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, "").count(os.sep)
        indent = " " * 4 * (level)
        print(f"{indent}{os.path.basename(root)}/")
        subindent = " " * 4 * (level + 1)
        for f in files:
            print(f"{subindent}{f}")


# Example usage:
print_directory_tree(os.getcwd())

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# extensions = []
extensions = ["sphinx.ext.autodoc", "sphinx_copybutton", "sphinx.ext.linkcode"]

# templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "alabaster"
# html_static_path = ["_static"]
