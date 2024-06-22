.. _conjure:

Conjure
=======
`Conjure` is a module for turning existing surveys, survey results and other data into EDSL objects.

For example, you can use it to turn a file of survey results into a `Results` object with an associated EDSL `Survey`, or a file of information about survey respondents or other populations into an `AgentList`.

Acceptable file formats for import are CSV (`.csv`), SPSS (`.sav`), and Stata (`.dta`).


How to use Conjure
------------------

1. Create a `Conjure` object by passing the path to the file you want to import. 

2. Use the `to_agent_list()`, `to_survey()`, or `to_results()` methods to create the desired EDSL objects.

3. Use the resulting EDSL objects as you would any other EDSL object, such as analyzing results or extending them with new survey questions for the agents.


Here we demonstrate these methods using the some results from a survey about shopping preferences, stored in a CSV file:

.. code-block:: text 

    UUID,Favorite_Store,Payment_Preference,Satisfaction_Online_Shopping,Preferred_Shopping_Day,Improvement_Suggestions
    123e4567-e89b-12d3-a456-426614174000,Walmart,Credit Card,4,Weekend,More frequent sales and discounts
    234f5678-f91c-23e4-b567-537725175101,Target,Debit Card,5,Weekday,Improve website navigation
    345a6789-g02d-34f5-c678-648836276202,Amazon,PayPal,3,Weekend,Offer free shipping
    456b7890-h13e-45g6-d789-759947377303,Costco,Cash,2,Weekend,Extend return policy
    567c8911-i24f-56h7-e890-860158478404,Local Boutique,Credit Card,5,Weekday,Add more product variety
    678d9022-j35g-67i8-f901-971269579505,Whole Foods,Debit Card,4,Weekend,Include more organic options
    789e0133-k46h-78j9-g012-082370680606,Best Buy,PayPal,3,Weekday,Enhance customer support
    890f1244-l57i-89k0-h123-193481781707,Trader Joe's,Cash,4,Weekend,Better parking facilities


First, we create a `Conjure` object by passing the path to the file:

.. code-block:: python

    from edsl import Conjure

    c = Conjure("example_survey_results.csv")


We can inspect some basic information about the new object:

.. code-block:: python

    c


Output:

.. code-block:: python

    InputDataCSV: datafile_name:'shopping_survey.csv' num_questions:6, num_agents:8


We can use the `to_agent_list()` method to generate an `AgentList` object inspect the agent list that is created:

.. code-block:: python

    agentlist = c.to_agent_list()

    agentlist


We can see that it is a list of dictionaries, where each dictionary represents an agent and contains (1) the agent's `traits` which are the agent's responses to the original survey and (2) a codebook that maps the new trait names to the original column names in the data file:

.. code-block:: python

    [
        {
            "traits": {
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "favorite_store": "Walmart",
                "payment_preference": "Credit Card",
                "satisfaction_online_shopp": 4,
                "preferred_shopping_day": "Weekend",
                "improvement_suggestions": "More frequent sales and discounts"
            },
            "codebook": {
                "uuid": "UUID",
                "favorite_store": "Favorite_Store",
                "payment_preference": "Payment_Preference",
                "satisfaction_online_shopp": "Satisfaction_Online_Shopping",
                "preferred_shopping_day": "Preferred_Shopping_Day",
                "improvement_suggestions": "Improvement_Suggestions"
            }
        },
        {
            "traits": {
                "uuid": "234f5678-f91c-23e4-b567-537725175101",
                "favorite_store": "Target",
                "payment_preference": "Debit Card",
                "satisfaction_online_shopp": 5,
                "preferred_shopping_day": "Weekday",
                "improvement_suggestions": "Improve website navigation"
            },
            "codebook": {
                "uuid": "UUID",
                "favorite_store": "Favorite_Store",
                "payment_preference": "Payment_Preference",
                "satisfaction_online_shopp": "Satisfaction_Online_Shopping",
                "preferred_shopping_day": "Preferred_Shopping_Day",
                "improvement_suggestions": "Improvement_Suggestions"
            }
        },
        {
            "traits": {
                "uuid": "345a6789-g02d-34f5-c678-648836276202",
                "favorite_store": "Amazon",
                "payment_preference": "PayPal",
                "satisfaction_online_shopp": 3,
                "preferred_shopping_day": "Weekend",
                "improvement_suggestions": "Offer free shipping"
            },
            "codebook": {
                "uuid": "UUID",
                "favorite_store": "Favorite_Store",
                "payment_preference": "Payment_Preference",
                "satisfaction_online_shopp": "Satisfaction_Online_Shopping",
                "preferred_shopping_day": "Preferred_Shopping_Day",
                "improvement_suggestions": "Improvement_Suggestions"
            }
        },
        {
            "traits": {
                "uuid": "456b7890-h13e-45g6-d789-759947377303",
                "favorite_store": "Costco",
                "payment_preference": "Cash",
                "satisfaction_online_shopp": 2,
                "preferred_shopping_day": "Weekend",
                "improvement_suggestions": "Extend return policy"
            },
            "codebook": {
                "uuid": "UUID",
                "favorite_store": "Favorite_Store",
                "payment_preference": "Payment_Preference",
                "satisfaction_online_shopp": "Satisfaction_Online_Shopping",
                "preferred_shopping_day": "Preferred_Shopping_Day",
                "improvement_suggestions": "Improvement_Suggestions"
            }
        },
        {
            "traits": {
                "uuid": "567c8911-i24f-56h7-e890-860158478404",
                "favorite_store": "Local Boutique",
                "payment_preference": "Credit Card",
                "satisfaction_online_shopp": 5,
                "preferred_shopping_day": "Weekday",
                "improvement_suggestions": "Add more product variety"
            },
            "codebook": {
                "uuid": "UUID",
                "favorite_store": "Favorite_Store",
                "payment_preference": "Payment_Preference",
                "satisfaction_online_shopp": "Satisfaction_Online_Shopping",
                "preferred_shopping_day": "Preferred_Shopping_Day",
                "improvement_suggestions": "Improvement_Suggestions"
            }
        },
        {
            "traits": {
                "uuid": "678d9022-j35g-67i8-f901-971269579505",
                "favorite_store": "Whole Foods",
                "payment_preference": "Debit Card",
                "satisfaction_online_shopp": 4,
                "preferred_shopping_day": "Weekend",
                "improvement_suggestions": "Include more organic options"
            },
            "codebook": {
                "uuid": "UUID",
                "favorite_store": "Favorite_Store",
                "payment_preference": "Payment_Preference",
                "satisfaction_online_shopp": "Satisfaction_Online_Shopping",
                "preferred_shopping_day": "Preferred_Shopping_Day",
                "improvement_suggestions": "Improvement_Suggestions"
            }
        },
        {
            "traits": {
                "uuid": "789e0133-k46h-78j9-g012-082370680606",
                "favorite_store": "Best Buy",
                "payment_preference": "PayPal",
                "satisfaction_online_shopp": 3,
                "preferred_shopping_day": "Weekday",
                "improvement_suggestions": "Enhance customer support"
            },
            "codebook": {
                "uuid": "UUID",
                "favorite_store": "Favorite_Store",
                "payment_preference": "Payment_Preference",
                "satisfaction_online_shopp": "Satisfaction_Online_Shopping",
                "preferred_shopping_day": "Preferred_Shopping_Day",
                "improvement_suggestions": "Improvement_Suggestions"
            }
        },
        {
            "traits": {
                "uuid": "890f1244-l57i-89k0-h123-193481781707",
                "favorite_store": "Trader Joe's",
                "payment_preference": "Cash",
                "satisfaction_online_shopp": 4,
                "preferred_shopping_day": "Weekend",
                "improvement_suggestions": "Better parking facilities"
            },
            "codebook": {
                "uuid": "UUID",
                "favorite_store": "Favorite_Store",
                "payment_preference": "Payment_Preference",
                "satisfaction_online_shopp": "Satisfaction_Online_Shopping",
                "preferred_shopping_day": "Preferred_Shopping_Day",
                "improvement_suggestions": "Improvement_Suggestions"
            }
        }
    ]


Here we inspect the components of the survey that was created:

.. code-block:: python

    survey.keys()


We can see that the survey has a list of questions, a memory plan, a rule collection, and question groups.

.. code-block:: python

    ['questions', 'memory_plan', 'rule_collection', 'question_groups']


We can inspect the full survey object or individual components:

.. code-block:: python 

    {
        "questions": [
            {
                "question_name": "uuid",
                "question_text": "UUID",
                "question_options": [
                    "456b7890-h13e-45g6-d789-759947377303",
                    "890f1244-l57i-89k0-h123-193481781707",
                    "234f5678-f91c-23e4-b567-537725175101",
                    "123e4567-e89b-12d3-a456-426614174000",
                    "567c8911-i24f-56h7-e890-860158478404",
                    "678d9022-j35g-67i8-f901-971269579505",
                    "345a6789-g02d-34f5-c678-648836276202",
                    "789e0133-k46h-78j9-g012-082370680606"
                ],
                "question_type": "multiple_choice",
                "edsl_version": "0.1.27.dev3",
                "edsl_class_name": "QuestionBase"
            },
            {
                "question_name": "favorite_store",
                "question_text": "Favorite_Store",
                "question_options": [
                    "Whole Foods",
                    "Walmart",
                    "Target",
                    "Amazon",
                    "Costco",
                    "Local Boutique",
                    "Trader Joe's",
                    "Best Buy"
                ],
                "question_type": "multiple_choice",
                "edsl_version": "0.1.27.dev3",
                "edsl_class_name": "QuestionBase"
            },
            {
                "question_name": "payment_preference",
                "question_text": "Payment_Preference",
                "question_options": [
                    "Cash",
                    "Credit Card",
                    "PayPal",
                    "Debit Card"
                ],
                "question_type": "multiple_choice",
                "edsl_version": "0.1.27.dev3",
                "edsl_class_name": "QuestionBase"
            },
            {
                "question_name": "satisfaction_online_shopp",
                "question_text": "Satisfaction_Online_Shopping",
                "question_options": [
                    "2",
                    "3",
                    "4",
                    "5"
                ],
                "question_type": "multiple_choice",
                "edsl_version": "0.1.27.dev3",
                "edsl_class_name": "QuestionBase"
            },
            {
                "question_name": "preferred_shopping_day",
                "question_text": "Preferred_Shopping_Day",
                "question_options": [
                    "Weekend",
                    "Weekday"
                ],
                "question_type": "multiple_choice",
                "edsl_version": "0.1.27.dev3",
                "edsl_class_name": "QuestionBase"
            },
            {
                "question_name": "improvement_suggestions",
                "question_text": "Improvement_Suggestions",
                "question_options": [
                    "Add more product variety",
                    "Extend return policy",
                    "Include more organic options",
                    "Better parking facilities",
                    "Improve website navigation",
                    "More frequent sales and discounts",
                    "Enhance customer support",
                    "Offer free shipping"
                ],
                "question_type": "multiple_choice",
                "edsl_version": "0.1.27.dev3",
                "edsl_class_name": "QuestionBase"
            }
        ]
    }


Using your "conjured" EDSL objects
----------------------------------

Once you have created an `AgentList`, `Survey`, or `Results` object from your `Conjure` object, you can use them as you would any other EDSL object. 

Here we administer a new question to the agent list that we created:

.. code-block:: python

    from edsl.questions import QuestionFreeText

    q = QuestionFreeText( 
        question_name = "how_are_you",
        question_text = "How are you?"
    )

    results = q.by(agentlist).run()


We can verify that the agent traits representing the original survey responses are components of the results
(see the components with the `agent.` prefix):


.. code-block:: python

    results.columns


Output: 

.. code-block:: python

    ['agent.agent_instruction',
    'agent.agent_name',
    'agent.favorite_store',
    'agent.improvement_suggestions',
    'agent.payment_preference',
    'agent.preferred_shopping_day',
    'agent.satisfaction_online_shopp',
    'agent.uuid',
    'answer.how_are_you',
    'iteration.iteration',
    'model.frequency_penalty',
    'model.logprobs',
    'model.max_tokens',
    'model.model',
    'model.presence_penalty',
    'model.temperature',
    'model.top_logprobs',
    'model.top_p',
    'prompt.how_are_you_system_prompt',
    'prompt.how_are_you_user_prompt',
    'question_options.how_are_you_question_options',
    'question_text.how_are_you_question_text',
    'question_type.how_are_you_question_type',
    'raw_model_response.how_are_you_raw_model_response']


We can inspect them together with the responses to the new question as usual:

.. code-block:: python

    results.select("uuid", "favorite_store", "payment_preference", "how_are_you").print(format="rich", max_rows=3) 


Output:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ agent                              ┃ agent           ┃ agent               ┃ answer                             ┃
    ┃ .uuid                              ┃ .favorite_store ┃ .payment_preference ┃ .how_are_you                       ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ 123e4567-e89b-12d3-a456-426614174… │ Walmart         │ Credit Card         │ I'm doing well, thank you! How     │
    │                                    │                 │                     │ about yourself?                    │
    ├────────────────────────────────────┼─────────────────┼─────────────────────┼────────────────────────────────────┤
    │ 234f5678-f91c-23e4-b567-537725175… │ Target          │ Debit Card          │ I'm doing great, thank you for     │
    │                                    │                 │                     │ asking! How can I assist you       │
    │                                    │                 │                     │ today?                             │
    ├────────────────────────────────────┼─────────────────┼─────────────────────┼────────────────────────────────────┤
    │ 345a6789-g02d-34f5-c678-648836276… │ Amazon          │ PayPal              │ I'm doing well, thank you! How can │
    │                                    │                 │                     │ I assist you today?                │
    └────────────────────────────────────┴─────────────────┴─────────────────────┴────────────────────────────────────┘



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