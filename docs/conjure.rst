.. _conjure:

Conjure
=======
`Conjure` is a module for turning existing surveys, survey results and other data into EDSL objects.

For example, you can use it to turn a file of survey results into a `Results` object with an associated EDSL `Survey`, or a file of information about survey respondents or other populations into an `AgentList`.

Acceptable file formats for import are CSV (`.csv`), SPSS (`.sav`), and Stata (`.dta`).


How to use Conjure
------------------
Create a `Conjure` object by passing the path to the file you want to import. 
Then use the `to_agent_list()`, `to_survey()`, or `to_results()` methods to create the desired EDSL object:

.. code-block:: python

    from edsl import Conjure
    
    c = Conjure("example_survey_results.csv")
    al = c.to_agent_list()
    survey = c.to_survey()
    results = c.to_results()



Conjure class
-------------
.. automodule:: edsl.conjure.Conjure
   :members:  
   :inherited-members:
   :exclude-members: 
   :undoc-members:
   :special-members: __init__


InputData class
---------------
.. automodule:: edsl.conjure.InputData
   :members:  
   :inherited-members:
   :exclude-members: 
   :undoc-members:
   :special-members: __init__