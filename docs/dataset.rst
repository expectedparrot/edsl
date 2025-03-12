.. _dataset:

Dataset
=======

The ``Dataset`` class is a versatile data container for tabular data with powerful manipulation capabilities. It represents data in a column-oriented format, providing methods for analysis, transformation, and visualization.

Overview
--------

Dataset is a fundamental data structure in EDSL that provides a column-oriented representation of tabular data. It offers methods for manipulating, analyzing, visualizing, and exporting data, similar to tools like pandas or dplyr.

Key features:

1. Flexible data manipulation (filtering, sorting, transformation)
2. Visualization capabilities with multiple rendering options
3. Export to various formats (CSV, Excel, Pandas, etc.)
4. Integration with other EDSL components

Creating Datasets
----------------

Datasets can be created from various sources:

From dictionaries:

.. code-block:: python

    from edsl import Dataset
    
    # Create a dataset with two columns
    d = Dataset([{'a': [1, 2, 3]}, {'b': [4, 5, 6]}])

From existing EDSL objects:

.. code-block:: python

    # From Results object
    dataset = results.select('how_feeling', 'agent.status')
    
    # From pandas DataFrame
    import pandas as pd
    df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
    dataset = Dataset.from_pandas_dataframe(df)

Displaying and Visualizing Data
------------------------------

The Dataset class provides multiple ways to display and visualize data:

Basic display:

.. code-block:: python

    # Print the dataset
    dataset.print()
    
    # Display only the first few rows
    dataset.head()
    
    # Display only the last few rows
    dataset.tail()

Table Display Options
---------------------

You can control the table formatting using the ``tablefmt`` parameter:

.. code-block:: python

    # Display as an ASCII grid
    dataset.table(tablefmt="grid")
    
    # Display as pipe-separated values
    dataset.table(tablefmt="pipe")
    
    # Display as HTML
    dataset.table(tablefmt="html")
    
    # Display as Markdown
    dataset.table(tablefmt="github")
    
    # Display as LaTeX
    dataset.table(tablefmt="latex")

Rich Terminal Output
^^^^^^^^^^^^^^^^^^^

The Dataset class supports displaying tables with enhanced formatting using the Rich library, which provides beautiful terminal formatting with colors, styles, and more:

.. code-block:: python

    # Display using Rich formatting
    dataset.table(tablefmt="rich")
    
    # Alternative syntax
    dataset.print(format="rich")

This creates a nicely formatted table in the terminal with automatically sized columns, bold headers, and grid lines.

Example:

.. code-block:: python

    from edsl import Dataset
    
    # Create a dataset
    d = Dataset([
        {'name': ['Alice', 'Bob', 'Charlie', 'David']},
        {'age': [25, 32, 45, 19]},
        {'city': ['New York', 'Los Angeles', 'Chicago', 'Boston']}
    ])
    
    # Display with rich formatting
    d.table(tablefmt="rich")

Data Manipulation
---------------

The Dataset class provides numerous methods for data manipulation:

Filtering:

.. code-block:: python

    # Filter results for a specific condition
    filtered = dataset.filter("how_feeling == 'Great'")

Creating new columns:

.. code-block:: python

    # Create a new column
    with_sentiment = dataset.mutate("sentiment = 1 if how_feeling == 'Great' else 0")

Sorting:

.. code-block:: python

    # Sort by a specific column
    sorted_data = dataset.order_by("age", reverse=True)

Reshaping:

.. code-block:: python

    # Convert to long format
    long_data = dataset.long()
    
    # Convert back to wide format
    wide_data = long_data.wide()

Exporting Data
------------

Export to various formats:

.. code-block:: python

    # Export to CSV
    dataset.to_csv("data.csv")
    
    # Export to pandas DataFrame
    df = dataset.to_pandas()
    
    # Export to Word document
    dataset.to_docx("data.docx", title="My Dataset")

Dataset Methods
-------------

.. autoclass:: edsl.dataset.Dataset
    :members:
    :undoc-members:
    :show-inheritance:
    :exclude-members: codebook, data