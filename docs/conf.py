# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys

import sphinx
import sphinx_rtd_theme
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
extensions = [
    "sphinx.ext.autodoc",
    "sphinx_copybutton",
    "sphinx.ext.linkcode",
    "nbsphinx",
]
nbsphinx_notebooks = ["../examples/*.ipynb"]
import glob

nbsphinx_notebooks = glob.glob("notebooks/*.ipynb")

# templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"  # "alabaster"
# html_static_path = ["_static"]
# html_theme_path = [sphinx_rtd_theme.get_html_theme_path()] # not needed, causes issue with search bar

html_theme_options = {
    "fixed_sidebar": True,
}

html_show_sphinx = False 

html_logo = "static/logo.png"

html_favicon = "static/favicon.ico"