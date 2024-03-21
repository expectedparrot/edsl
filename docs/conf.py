# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import sys
import os

project = 'edsl'
copyright = '2024 Expected Parrot, Inc.'
author = 'Expected Parrot, Inc.'

print("Current working directory:")
print(os.getcwd())

print("System path:")
print(sys.path)

#sys.path.insert(0, os.path.abspath(os.path.join("..", "..", "edsl")))
#sys.path.insert(0, os.path.abspath(os.path.join("..", "..")))

sys.path.insert(0, os.path.abspath("../"))
#sys.path.insert(0, os.path.abspath('..'))
#sys.path.insert(0, os.path.abspath('../..'))
#sys.path.insert(0, os.path.abspath('../../../'))
print("System path after insert:")
print(sys.path)


import os

def print_directory_tree(startpath):
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        print(f'{indent}{os.path.basename(root)}/')
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            print(f'{subindent}{f}')

# Example usage:
print_directory_tree(os.getcwd())

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

#extensions = []
extensions = [
    'sphinx.ext.autodoc', 'sphinx_copybutton'
    # other extensions...
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']
