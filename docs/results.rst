.. _results:

Results
=======

.. The Results object is the result of running a survey. 
.. It is not typically instantiated directly, but is returned by the run method of a `Job` object.

.. code-block:: python

   job = Job.example()
   results = job.run()

It is a list of Result objects, each of which represents a single response to the survey and can be manipulated like a list.

Creating tables by selecting and printing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A results object has many 'columns' that can be selected and printed.
For example, to print a table of the `how_feeling` column:

.. code-block:: python

   results = Results.example()
   results.select("how_feeling").print()

This will print a table of the `how_feeling` column.

.. code-block:: text

   ┏━━━━━━━━━━━━━━┓
   ┃ answer       ┃
   ┃ .how_feeling ┃
   ┡━━━━━━━━━━━━━━┩
   │ OK           │
   ├──────────────┤
   │ Great        │
   ├──────────────┤
   │ Terrible     │
   ├──────────────┤
   │ OK           │
   └──────────────┘

Filtering
^^^^^^^^^

You can filter the results by using the `filter` method.

.. code-block:: python

    results = Results.example()
    results.filter("how_feeling == 'Great'").select("how_feeling").print()

which will print a table of the `how_feeling` column where the value is 'Great'.

.. code-block:: text

   ┏━━━━━━━━━━━━━━┓
   ┃ answer       ┃
   ┃ .how_feeling ┃
   ┡━━━━━━━━━━━━━━┩
   │ Great        │
   └──────────────┘    


Interacting via SQL
^^^^^^^^^^^^^^^^^^^
You can interact with the results via SQL.

.. code-block:: python

   results = Results.example()
   results.sql("select data_type, key, value from self where data_type = 'answer' limit 3", shape="long")


Exporting to other formats (pandas, csv, etc.)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can export the results to other formats, such as pandas DataFrames or csv files.

.. code-block:: python

   results = Results.example()
   results.to_pandas()


Results class
-------------

.. automodule:: edsl.results.Results
   :members:
   :inherited-members:
   :exclude-members: append, clear, copy, count, extend, index, insert, pop, remove, reverse, sort, known_data_types, Mixins, main
   :undoc-members:
   :special-members: __init__


.. Dataset class
.. -------------

.. .. automodule:: edsl.results.Dataset
..    :members:
..    :undoc-members:
..    :show-inheritance:

.. ResultsDBMixin class
.. --------------------

.. .. automodule:: edsl.results.ResultsDBMixin
..    :members:
..    :undoc-members:
..    :show-inheritance:

.. ResultsExportMixin class
.. ------------------------

.. .. automodule:: edsl.results.ResultsExportMixin
..    :members:
..    :undoc-members:
..    :show-inheritance:

.. ResultsGGMixin class
.. --------------------

.. .. automodule:: edsl.results.ResultsGGMixin
..    :members:
..    :undoc-members:
..    :show-inheritance:
