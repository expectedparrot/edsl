# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import glob
import os
import sys

project = "edsl"
copyright = "2024 Expected Parrot, Inc"
author = "Expected Parrot, Inc."

print(f"Current working directory: {os.getcwd()}")
print(f"System path: {sys.path}")
sys.path.insert(0, os.path.abspath("../"))
print(f"System path after insert: {sys.path}")

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
# print_directory_tree(os.getcwd())


def setup(app):
    app.add_css_file(
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"
    )


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
extensions = [
    "sphinx.ext.autodoc",
    "sphinx_copybutton",
    "sphinx.ext.linkcode",
    "nbsphinx",
    "sphinx_fontawesome",
    "myst_parser",
]
nbsphinx_notebooks = ["../examples/*.ipynb"]
nbsphinx_notebooks = glob.glob("notebooks/*.ipynb")
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
html_theme = "sphinx_rtd_theme"
html_theme_options = {"display_version": False}
html_show_sphinx = False
html_show_sourcelink = False
html_logo = "static/logo.png"
html_favicon = "static/favicon.ico"

html_context = {
    "display_github": False,
    "github_user": "",
    "github_repo": "",
    "github_version": "",
}

nbsphinx_allow_errors = True