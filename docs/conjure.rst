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
    agentlist = c.to_agent_list()
    survey = c.to_survey()
    results = c.to_results()


We can inspect the agent list that was created:

.. code-block:: python

    agentlist


Output:

.. code-block:: python

    [
        {
            "traits": {
                "respondent_name": "Alon",
                "old": 50,
                "live": "New York City",
                "favorite_kind_music": "Pop"
            },
            "codebook": {
                "respondent_name": "Name",
                "old": "How old are you?",
                "live": "Where do you live?",
                "favorite_kind_music": "What is your favorite kind of music?"
            }
        },
        {
            "traits": {
                "respondent_name": "Barb",
                "old": 25,
                "live": "Cambridge",
                "favorite_kind_music": "Indie"
            },
            "codebook": {
                "respondent_name": "Name",
                "old": "How old are you?",
                "live": "Where do you live?",
                "favorite_kind_music": "What is your favorite kind of music?"
            }
        },
        {
            "traits": {
                "respondent_name": "Cary",
                "old": 64,
                "live": "Toronto",
                "favorite_kind_music": "Classical"
            },
            "codebook": {
                "respondent_name": "Name",
                "old": "How old are you?",
                "live": "Where do you live?",
                "favorite_kind_music": "What is your favorite kind of music?"
            }
        },
        {
            "traits": {
                "respondent_name": "Doug",
                "old": 45,
                "live": "London",
                "favorite_kind_music": "Country"
            },
            "codebook": {
                "respondent_name": "Name",
                "old": "How old are you?",
                "live": "Where do you live?",
                "favorite_kind_music": "What is your favorite kind of music?"
            }
        },
        {
            "traits": {
                "respondent_name": "Evan",
                "old": 81,
                "live": "Paris",
                "favorite_kind_music": "Jazz"
            },
            "codebook": {
                "respondent_name": "Name",
                "old": "How old are you?",
                "live": "Where do you live?",
                "favorite_kind_music": "What is your favorite kind of music?"
            }
        }
    ]


Here we inspect the survey that was created:

.. code-block:: python

    survey


Output:

.. code-block:: python 

    {
        "questions": [
            {
                "question_name": "respondent_name",
                "question_text": "Name",
                "question_options": [
                    "Evan",
                    "Alon",
                    "Barb",
                    "Doug",
                    "Cary"
                ],
                "question_type": "multiple_choice",
                "edsl_version": "0.1.27.dev3",
                "edsl_class_name": "QuestionBase"
            },
            {
                "question_name": "old",
                "question_text": "How old are you?",
                "question_options": [
                    "64",
                    "45",
                    "81",
                    "50",
                    "25"
                ],
                "question_type": "multiple_choice",
                "edsl_version": "0.1.27.dev3",
                "edsl_class_name": "QuestionBase"
            },
            {
                "question_name": "live",
                "question_text": "Where do you live?",
                "question_options": [
                    "Paris",
                    "New York City",
                    "Cambridge",
                    "Toronto",
                    "London"
                ],
                "question_type": "multiple_choice",
                "edsl_version": "0.1.27.dev3",
                "edsl_class_name": "QuestionBase"
            },
            {
                "question_name": "favorite_kind_music",
                "question_text": "What is your favorite kind of music?",
                "question_options": [
                    "Indie",
                    "Jazz",
                    "Pop",
                    "Country",
                    "Classical"
                ],
                "question_type": "multiple_choice",
                "edsl_version": "0.1.27.dev3",
                "edsl_class_name": "QuestionBase"
            }
        ],
        "memory_plan": {
            "survey_question_names": [
                "respondent_name",
                "old",
                "live",
                "favorite_kind_music"
            ],
            "survey_question_texts": [
                "Name",
                "How old are you?",
                "Where do you live?",
                "What is your favorite kind of music?"
            ],
            "data": {}
        },
        "rule_collection": {
            "rules": [
                {
                    "current_q": 0,
                    "expression": "True",
                    "next_q": 1,
                    "priority": -1,
                    "question_name_to_index": {
                        "respondent_name": 0
                    },
                    "before_rule": false,
                    "edsl_version": "0.1.27.dev3",
                    "edsl_class_name": "Rule"
                },
                {
                    "current_q": 1,
                    "expression": "True",
                    "next_q": 2,
                    "priority": -1,
                    "question_name_to_index": {
                        "respondent_name": 0,
                        "old": 1
                    },
                    "before_rule": false,
                    "edsl_version": "0.1.27.dev3",
                    "edsl_class_name": "Rule"
                },
                {
                    "current_q": 2,
                    "expression": "True",
                    "next_q": 3,
                    "priority": -1,
                    "question_name_to_index": {
                        "respondent_name": 0,
                        "old": 1,
                        "live": 2
                    },
                    "before_rule": false,
                    "edsl_version": "0.1.27.dev3",
                    "edsl_class_name": "Rule"
                },
                {
                    "current_q": 3,
                    "expression": "True",
                    "next_q": 4,
                    "priority": -1,
                    "question_name_to_index": {
                        "respondent_name": 0,
                        "old": 1,
                        "live": 2,
                        "favorite_kind_music": 3
                    },
                    "before_rule": false,
                    "edsl_version": "0.1.27.dev3",
                    "edsl_class_name": "Rule"
                }
            ],
            "num_questions": null
        },
        "question_groups": {}
    }



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