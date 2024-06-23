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


Example 
^^^^^^^
Here we demonstrate these methods using the some results from a survey about shopping preferences, stored in a CSV file.
The file contains a respondent 'UUID' column and 5 columns of survey responses. The first row contains the column names:

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


Create a `Conjure` object
^^^^^^^^^^^^^^^^^^^^^^^^^
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


Create an `AgentList`
^^^^^^^^^^^^^^^^^^^^^
We can use the `to_agent_list()` method to generate an `AgentList` object from the `Conjure` object:

.. code-block:: python

    agentlist = c.to_agent_list()


We can verify the object type:

    type(agentlist)


Output:

.. code-block:: python

    edsl.agents.AgentList.AgentList


We can confirm that the components of the agent list are individual `Agent` objects:

.. code-block:: python

    type(agentlist[0])


Output:

.. code-block:: python

    edsl.agents.Agent.Agent


The `AgentList` is a list of dictionaries, where each dictionary represents an agent and contains (1) the individual agent's `traits` and (2) a `codebook` for the original survey.
The `traits` are a dictionary with keys representing the original column names in the file and values that are the agent's data/responses to each question.
The `codebook` is a dictionary mapping the new trait names to the original column names in the data file:

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


Create an `Survey`
^^^^^^^^^^^^^^^^^^^^^
We can use the `to_survey()` method to generate a `Survey` object from the `Conjure` object:

.. code-block:: python

    survey = c.to_survey()


We can inspect the components of the survey that was created:

.. code-block:: python

    survey.keys()


Output:

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



Create a `Results` object
^^^^^^^^^^^^^^^^^^^^^^^^^

We can use the `to_results()` method to generate a `Results` object from the `Conjure` object:

.. code-block:: python

    results = c.to_results()


We can review a list the components of the results that were created:

.. code-block:: python

    results.columns


We can see that the columns of the original file have been stored as questions and answers in the results object:

.. code-block:: python 

    ['agent.agent_instruction',
    'agent.agent_name',
    'answer.favorite_store',
    'answer.improvement_suggestions',
    'answer.payment_preference',
    'answer.preferred_shopping_day',
    'answer.satisfaction_online_shopp',
    'answer.uuid',
    'comment.favorite_store_comment',
    'comment.improvement_suggestions_comment',
    'comment.payment_preference_comment',
    'comment.preferred_shopping_day_comment',
    'comment.satisfaction_online_shopp_comment',
    'comment.uuid_comment',
    'iteration.iteration',
    'model.frequency_penalty',
    'model.logprobs',
    'model.max_tokens',
    'model.model',
    'model.presence_penalty',
    'model.temperature',
    'model.top_logprobs',
    'model.top_p',
    'prompt.favorite_store_system_prompt',
    'prompt.favorite_store_user_prompt',
    'prompt.improvement_suggestions_system_prompt',
    'prompt.improvement_suggestions_user_prompt',
    'prompt.payment_preference_system_prompt',
    'prompt.payment_preference_user_prompt',
    'prompt.preferred_shopping_day_system_prompt',
    'prompt.preferred_shopping_day_user_prompt',
    'prompt.satisfaction_online_shopp_system_prompt',
    'prompt.satisfaction_online_shopp_user_prompt',
    'prompt.uuid_system_prompt',
    'prompt.uuid_user_prompt',
    'question_options.favorite_store_question_options',
    'question_options.improvement_suggestions_question_options',
    'question_options.payment_preference_question_options',
    'question_options.preferred_shopping_day_question_options',
    'question_options.satisfaction_online_shopp_question_options',
    'question_options.uuid_question_options',
    'question_text.favorite_store_question_text',
    'question_text.improvement_suggestions_question_text',
    'question_text.payment_preference_question_text',
    'question_text.preferred_shopping_day_question_text',
    'question_text.satisfaction_online_shopp_question_text',
    'question_text.uuid_question_text',
    'question_type.favorite_store_question_type',
    'question_type.improvement_suggestions_question_type',
    'question_type.payment_preference_question_type',
    'question_type.preferred_shopping_day_question_type',
    'question_type.satisfaction_online_shopp_question_type',
    'question_type.uuid_question_type',
    'raw_model_response.favorite_store_raw_model_response',
    'raw_model_response.improvement_suggestions_raw_model_response',
    'raw_model_response.payment_preference_raw_model_response',
    'raw_model_response.preferred_shopping_day_raw_model_response',
    'raw_model_response.satisfaction_online_shopp_raw_model_response',
    'raw_model_response.uuid_raw_model_response']



Editing the "conjured" objects 
------------------------------
*In progress*



Using your "conjured" EDSL objects
----------------------------------

Once you have created an `AgentList`, `Survey`, or `Results` object from your `Conjure` object, you can use them as you would any other EDSL object. 

Here we administer a new question to the agent list that we created that checks that the agent understands its traits:

.. code-block:: python

    from edsl.questions import QuestionFreeText

    q = QuestionFreeText(
        question_name = "more_store",
        question_text = "What do you love most about your favorite store?"
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
    'answer.more_store',
    'iteration.iteration',
    'model.frequency_penalty',
    'model.logprobs',
    'model.max_tokens',
    'model.model',
    'model.presence_penalty',
    'model.temperature',
    'model.top_logprobs',
    'model.top_p',
    'prompt.more_store_system_prompt',
    'prompt.more_store_user_prompt',
    'question_options.more_store_question_options',
    'question_text.more_store_question_text',
    'question_type.more_store_question_type',
    'raw_model_response.more_store_raw_model_response']


We can inspect them together with the responses to the new question as usual:

.. code-block:: python

    results.select("favorite_store", "more_store").print(format="rich").print(format="rich", max_rows=3) 


Output:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ agent           ┃ answer                                                                                        ┃
    ┃ .favorite_store ┃ .more_store                                                                                   ┃
    ┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ Whole Foods     │ What I love most about Whole Foods is their commitment to quality and the wide variety of     │
    │                 │ organic products they offer. It aligns with my preference for healthy, natural foods and I    │
    │                 │ appreciate their efforts to source environmentally sustainable goods. The store's environment │
    │                 │ is also very pleasant, which makes the shopping experience enjoyable.                         │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Amazon          │ What I love most about my favorite store, Amazon, is the vast selection of products           │
    │                 │ available. They have everything from books to electronics, home goods, and even groceries.    │
    │                 │ The convenience of finding almost anything I need in one place is unparalleled. Additionally, │
    │                 │ the user reviews are incredibly helpful for making informed purchasing decisions.             │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Costco          │ What I love most about my favorite store, Costco, is the combination of high-quality          │
    │                 │ products, bulk purchasing options, and the substantial savings I get from buying in larger    │
    │                 │ quantities. Additionally, the wide variety of items available means I can often find          │
    │                 │ everything I need in one place, from groceries to electronics. The free samples are a fun     │
    │                 │ perk, too!                                                                                    │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Best Buy        │ What I love most about Best Buy is their wide selection of electronics and gadgets. It's like │
    │                 │ a playground for tech enthusiasts where I can find the latest devices and accessories. I also │
    │                 │ appreciate their price match guarantee, which gives me confidence that I'm getting a good     │
    │                 │ deal. Plus, their staff is generally knowledgeable and can help with technical questions I    │
    │                 │ might have.                                                                                   │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Local Boutique  │ What I love most about my favorite local boutique is the unique selection of items that you   │
    │                 │ just can't find anywhere else. They have a curated assortment of clothing and accessories     │
    │                 │ that really stand out because of their quality and originality. The store has a personal      │
    │                 │ touch, and the shopping experience feels intimate and special. Plus, their customer service   │
    │                 │ is exceptional; the staff are always friendly, knowledgeable, and willing to help with        │
    │                 │ anything I need.                                                                              │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Trader Joe's    │ What I love most about Trader Joe's is their unique selection of products that you can't find │
    │                 │ anywhere else. They offer a variety of organic and non-GMO options, which is important to me. │
    │                 │ The store also has a friendly and welcoming atmosphere, with helpful staff who seem genuinely │
    │                 │ happy to assist customers. Plus, their prices are reasonable for the quality of goods you     │
    │                 │ get, making it a great value overall.                                                         │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Walmart         │ What I love most about my favorite store, Walmart, is the convenience and variety it offers.  │
    │                 │ I can find almost everything I need under one roof, from groceries to electronics, which      │
    │                 │ saves me a lot of time. Additionally, the prices are competitive, and there's a good chance   │
    │                 │ of finding a deal or a discount on the products I'm looking for, especially on the weekends   │
    │                 │ when I prefer to do my shopping.                                                              │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Target          │ What I love most about my favorite store, Target, is the variety of products they offer, all  │
    │                 │ under one roof. It's incredibly convenient to find everything from clothing and electronics   │
    │                 │ to groceries and home goods. Additionally, the store layout is well-organized, which makes    │
    │                 │ shopping there a pleasant and efficient experience. The competitive pricing and exclusive     │
    │                 │ brands also add to the appeal, making it a go-to for both essentials and fun finds.           │
    └─────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────┘



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