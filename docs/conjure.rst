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

    What is your favorite store?,What is your preferred method of payment?,Rate your satisfaction with shopping options.,What is your preferred shopping day?,Do you have any suggestions for improvements in shopping options?
    Walmart,Credit Card,4,Weekend,More frequent sales and discounts
    Target,Debit Card,5,Weekday,Improve website navigation
    Amazon,PayPal,3,Weekend,Offer free shipping
    Costco,Cash,2,Weekend,Extend return policy
    Local Boutique,Credit Card,5,Weekday,Add more product variety
    Whole Foods,Debit Card,4,Weekend,Include more organic options
    Best Buy,PayPal,3,Weekday,Enhance customer support
    Trader Joe's,Cash,4,Weekend,Better parking facilities


Create a `Conjure` object
^^^^^^^^^^^^^^^^^^^^^^^^^
First, we create a `Conjure` object by passing the path to the file:

.. code-block:: python

    from edsl import Conjure

    c = Conjure("my_survey.csv")


We can inspect some basic information about the new object:

.. code-block:: python

    c


Output:

.. code-block:: python

    InputDataCSV: datafile_name:'my_survey.csv' num_questions:5, num_agents:8


We can get some basic statistics about the questions:

.. code-block:: python

    c.question_statistics("preferred_method_payment")


Output:

.. code-block:: python

    QuestionStats(num_responses=8, num_unique_responses=4, missing=0, unique_responses=['Credit Card', 'Cash', 'PayPal', 'Debit Card'], frac_numerical=0.0, top_5=[('Credit Card', 2), ('Debit Card', 2), ('PayPal', 2), ('Cash', 2)], frac_obs_from_top_5=1.0)


Create an AgentList
^^^^^^^^^^^^^^^^^^^
We can use the `to_agent_list()` method to generate an `AgentList` object from the `Conjure` object:

.. code-block:: python

    agents = c.to_agent_list()


The `AgentList` is a list of dictionaries, where each dictionary represents an agent and contains (1) the individual agent's `traits` and (2) a `codebook` for the original survey.
The `traits` are a dictionary with keys representing the original column names in the file and values that are the agent's data/responses to each question.
The `codebook` is a dictionary mapping the new trait names to the original column names in the data file:

We can inspect the components of the agent list that was created and individual agents:

.. code-block:: python

    agents[0]


Output:

.. code-block:: python

    {
        "traits": {
            "favorite_store": "Walmart",
            "preferred_method_payment": "Credit Card",
            "rate_satisfaction_shoppin": 4,
            "preferred_shopping_day": "Weekend",
            "suggestions_improvements": "More frequent sales and discounts"
        },
        "codebook": {
            "favorite_store": "What is your favorite store?",
            "preferred_method_payment": "What is your preferred method of payment?",
            "rate_satisfaction_shoppin": "Rate your satisfaction with shopping options.",
            "preferred_shopping_day": "What is your preferred shopping day?",
            "suggestions_improvements": "Do you have any suggestions for improvements in shopping options?"
        }
    }


Create a Survey
^^^^^^^^^^^^^^^
We can use the `to_survey()` method to generate a `Survey` object from the `Conjure` object:

.. code-block:: python

    survey = c.to_survey()


We can inspect the full survey object or individual components:

.. code-block:: python

    survey


Output:

.. code-block:: python 

    {
        "questions": [
            {
                "question_name": "favorite_store",
                "question_text": "What is your favorite store?",
                "question_options": [
                    "Target",
                    "Local Boutique",
                    "Walmart",
                    "Trader Joe's",
                    "Costco",
                    "Amazon",
                    "Best Buy",
                    "Whole Foods"
                ],
                "question_type": "multiple_choice"
            },
            {
                "question_name": "preferred_method_payment",
                "question_text": "What is your preferred method of payment?",
                "question_options": [
                    "Credit Card",
                    "Cash",
                    "PayPal",
                    "Debit Card"
                ],
                "question_type": "multiple_choice"
            },
            {
                "question_name": "rate_satisfaction_shoppin",
                "question_text": "Rate your satisfaction with shopping options.",
                "question_options": [
                    "2",
                    "3",
                    "4",
                    "5"
                ],
                "question_type": "multiple_choice"
            },
            {
                "question_name": "preferred_shopping_day",
                "question_text": "What is your preferred shopping day?",
                "question_options": [
                    "Weekend",
                    "Weekday"
                ],
                "question_type": "multiple_choice"
            },
            {
                "question_name": "suggestions_improvements",
                "question_text": "Do you have any suggestions for improvements in shopping options?",
                "question_options": [
                    "Add more product variety",
                    "Enhance customer support",
                    "More frequent sales and discounts",
                    "Improve website navigation",
                    "Extend return policy",
                    "Include more organic options",
                    "Offer free shipping",
                    "Better parking facilities"
                ],
                "question_type": "multiple_choice"
            }
        ],
        "memory_plan": {
            "survey_question_names": [
                "favorite_store",
                "preferred_method_payment",
                "rate_satisfaction_shoppin",
                "preferred_shopping_day",
                "suggestions_improvements"
            ],
            "survey_question_texts": [
                "What is your favorite store?",
                "What is your preferred method of payment?",
                "Rate your satisfaction with shopping options.",
                "What is your preferred shopping day?",
                "Do you have any suggestions for improvements in shopping options?"
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
                        "favorite_store": 0
                    },
                    "before_rule": false,
                    "edsl_version": "0.1.27",
                    "edsl_class_name": "Rule"
                },
                {
                    "current_q": 1,
                    "expression": "True",
                    "next_q": 2,
                    "priority": -1,
                    "question_name_to_index": {
                        "favorite_store": 0,
                        "preferred_method_payment": 1
                    },
                    "before_rule": false,
                    "edsl_version": "0.1.27",
                    "edsl_class_name": "Rule"
                },
                {
                    "current_q": 2,
                    "expression": "True",
                    "next_q": 3,
                    "priority": -1,
                    "question_name_to_index": {
                        "favorite_store": 0,
                        "preferred_method_payment": 1,
                        "rate_satisfaction_shoppin": 2
                    },
                    "before_rule": false,
                    "edsl_version": "0.1.27",
                    "edsl_class_name": "Rule"
                },
                {
                    "current_q": 3,
                    "expression": "True",
                    "next_q": 4,
                    "priority": -1,
                    "question_name_to_index": {
                        "favorite_store": 0,
                        "preferred_method_payment": 1,
                        "rate_satisfaction_shoppin": 2,
                        "preferred_shopping_day": 3
                    },
                    "before_rule": false,
                    "edsl_version": "0.1.27",
                    "edsl_class_name": "Rule"
                },
                {
                    "current_q": 4,
                    "expression": "True",
                    "next_q": 5,
                    "priority": -1,
                    "question_name_to_index": {
                        "favorite_store": 0,
                        "preferred_method_payment": 1,
                        "rate_satisfaction_shoppin": 2,
                        "preferred_shopping_day": 3,
                        "suggestions_improvements": 4
                    },
                    "before_rule": false,
                    "edsl_version": "0.1.27",
                    "edsl_class_name": "Rule"
                }
            ],
            "num_questions": null
        },
        "question_groups": {}
    }


Create Results
^^^^^^^^^^^^^^

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
    'agent.favorite_store',
    'agent.preferred_method_payment',
    'agent.preferred_shopping_day',
    'agent.rate_satisfaction_shoppin',
    'agent.suggestions_improvements',
    'answer.follow_up',
    'iteration.iteration',
    'model.frequency_penalty',
    'model.logprobs',
    'model.max_tokens',
    'model.model',
    'model.presence_penalty',
    'model.temperature',
    'model.top_logprobs',
    'model.top_p',
    'prompt.follow_up_system_prompt',
    'prompt.follow_up_user_prompt',
    'question_options.follow_up_question_options',
    'question_text.follow_up_question_text',
    'question_type.follow_up_question_type',
    'raw_model_response.follow_up_raw_model_response',
    'scenario.original_q']


Editing the "conjured" objects 
------------------------------
We can use the `rename()` and `rename_questions()` methods to edit the components of the `Conjure` object.
For example, we can change the question names that were generated:

.. code-block:: python

    c.rename_questions({"rate_satisfaction_shoppin": "shopping_satisfaction"})



Using your "conjured" EDSL objects
----------------------------------

Once you have created an `AgentList`, `Survey`, or `Results` object from your `Conjure` object, you can use them as you would any other EDSL object. 

Here we administer a new question to the agents that we created above, a follow-up to one of the original questions:

.. code-block:: python

    from edsl.questions import QuestionFreeText

    q = QuestionFreeText(
        question_name = "more_store",
        question_text = "What do you love most about your favorite store?"
    )

    results = q.by(agents).run()


We can verify that the agent traits representing the original survey responses are components of the results
(see the components with the `agent.` prefix):


.. code-block:: python

    results.columns


Output: 

.. code-block:: python

    ['agent.agent_instruction',
    'agent.agent_name',
    'agent.favorite_store',
    'agent.preferred_method_payment',
    'agent.preferred_shopping_day',
    'agent.rate_satisfaction_shoppin',
    'agent.suggestions_improvements',
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
    │ Costco          │ What I love most about Costco is the bulk buying options which offer great value for money,   │
    │                 │ the quality of their in-house brand Kirkland Signature, and the wide variety of products      │
    │                 │ available under one roof. Additionally, the free samples and the food court make for a        │
    │                 │ pleasant shopping experience.                                                                 │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Local Boutique  │ What I love most about my favorite local boutique is the unique selection of items that you   │
    │                 │ can't find anywhere else. Each piece feels special and curated, and I appreciate the personal │
    │                 │ touch that the store adds to the shopping experience. It's like discovering a treasure trove  │
    │                 │ of fashionable gems every time I visit.                                                       │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Trader Joe's    │ What I love most about Trader Joe's is their unique selection of products that you can't find │
    │                 │ anywhere else. The store offers a variety of organic and non-GMO options, which is important  │
    │                 │ to me. I also appreciate the friendly and helpful staff who always make shopping there a      │
    │                 │ pleasant experience. Plus, their prices are reasonable for the quality you get, making it a   │
    │                 │ great value overall.                                                                          │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Whole Foods     │ What I love most about Whole Foods is their commitment to providing a wide range of           │
    │                 │ high-quality, natural, and organic foods. The store's atmosphere is welcoming, and it offers  │
    │                 │ a variety of sustainable and eco-friendly products that align with my values. Additionally,   │
    │                 │ their fresh produce section is always stocked with a great selection of organic fruits and    │
    │                 │ vegetables, which is very important to me.                                                    │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Amazon          │ What I love most about my favorite store, Amazon, is the vast selection of products           │
    │                 │ available. I can find almost anything I need, from electronics to groceries, which is         │
    │                 │ incredibly convenient. The user reviews and ratings help me make informed decisions, and the  │
    │                 │ personalized recommendations often introduce me to items that I didn't even know I needed.    │
    │                 │ Plus, the convenience of having everything delivered to my door is a huge plus.               │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Target          │ What I love most about Target is the wide variety of products they offer, from groceries to   │
    │                 │ home goods, electronics, and clothing. I can usually find everything I need in one trip.      │
    │                 │ Plus, the store layout is well-organized, which makes shopping efficient and enjoyable. Their │
    │                 │ customer service is also generally very good, with helpful and friendly staff.                │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Best Buy        │ What I love most about Best Buy is their wide selection of electronics and gadgets. It's like │
    │                 │ a one-stop-shop for all the latest tech, which means I can usually find whatever I'm looking  │
    │                 │ for in one trip. Plus, they often have knowledgeable staff who can help answer my questions   │
    │                 │ about the products.                                                                           │
    ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
    │ Walmart         │ What I love most about Walmart is the convenience it offers with its wide range of products.  │
    │                 │ From groceries to electronics, I can find almost everything I need in one place. The prices   │
    │                 │ are also quite competitive, which is great for budget-conscious shoppers like me.             │
    │                 │ Additionally, the store layout is usually well-organized, making it easy to find what I'm     │
    │                 │ looking for. The fact that it's open late is a bonus, as it fits my busy schedule, especially │
    │                 │ on weekends.                                                                                  │
    └─────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────┘


We can also reference original questions as scenarios of new questions:

.. code-block:: python

    from edsl.questions import QuestionFreeText
    from edsl import Scenario

    q = QuestionFreeText(
        question_name = "follow_up",
        question_text = "Tell me more about your response to the question '{{ original_q }}'"
    )
    s = [Scenario({"original_q": q.question_text}) for q in survey.questions]

    results = q.by(s).by(agents).run()

    (results
    .filter("agent_name == 'Agent_0'") # Filter results by any fields
    .select("agent_name", "original_q", "follow_up") # Select components to inspect
    .print(pretty_labels = {"original_q":"Original question", "follow_up":"Follow-up question"},
            format="rich") 
    )


Output:

.. code-block:: text
    
    ┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ agent       ┃ scenario                                        ┃ answer                                          ┃
    ┃ .agent_name ┃ .original_q                                     ┃ .follow_up                                      ┃
    ┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ Agent_0     │ What is your favorite store?                    │ My favorite store is Walmart because it offers  │
    │             │                                                 │ a wide variety of products at competitive       │
    │             │                                                 │ prices, all under one roof. It's convenient for │
    │             │                                                 │ getting everything from groceries to            │
    │             │                                                 │ electronics, and I appreciate their consistent  │
    │             │                                                 │ stock and the availability of many brands.      │
    │             │                                                 │ Plus, their store layout is generally           │
    │             │                                                 │ shopper-friendly, making it easy to find what I │
    │             │                                                 │ need.                                           │
    ├─────────────┼─────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
    │ Agent_0     │ What is your preferred method of payment?       │ My preferred method of payment is using a       │
    │             │                                                 │ credit card. It's convenient, secure, and I can │
    │             │                                                 │ track my expenses easily. Plus, I enjoy the     │
    │             │                                                 │ benefits of reward points and the ability to    │
    │             │                                                 │ handle larger purchases that I might not want   │
    │             │                                                 │ to pay for all at once.                         │
    ├─────────────┼─────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
    │ Agent_0     │ Rate your satisfaction with shopping options.   │ I would rate my satisfaction with shopping      │
    │             │                                                 │ options as fairly high, around a 4 out of 5.    │
    │             │                                                 │ There's a good variety of products and I can    │
    │             │                                                 │ usually find what I need, but there's always    │
    │             │                                                 │ room for improvement, like having more frequent │
    │             │                                                 │ sales and discounts to enhance the shopping     │
    │             │                                                 │ experience.                                     │
    ├─────────────┼─────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
    │ Agent_0     │ What is your preferred shopping day?            │ My preferred shopping day is the weekend. I     │
    │             │                                                 │ find that weekends are more convenient for me   │
    │             │                                                 │ to browse through stores at a leisurely pace    │
    │             │                                                 │ without the rush of weekday commitments. It's   │
    │             │                                                 │ the time when I can take a moment to carefully  │
    │             │                                                 │ select items I need, compare prices, and enjoy  │
    │             │                                                 │ any in-store promotions that might be           │
    │             │                                                 │ happening. Plus, it's a nice break from the     │
    │             │                                                 │ weekly routine.                                 │
    ├─────────────┼─────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
    │ Agent_0     │ Do you have any suggestions for improvements in │ I think having more frequent sales and          │
    │             │ shopping options?                               │ discounts would greatly improve the shopping    │
    │             │                                                 │ experience. It would not only give customers    │
    │             │                                                 │ like me more value for our money but also       │
    │             │                                                 │ encourage us to shop more often. Additionally,  │
    │             │                                                 │ these promotions could be a way to clear out    │
    │             │                                                 │ inventory, making room for new and different    │
    │             │                                                 │ products.                                       │
    └─────────────┴─────────────────────────────────────────────────┴─────────────────────────────────────────────────┘


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