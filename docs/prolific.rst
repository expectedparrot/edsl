.. _prolific:

Prolific studies
================

Your Coop account provides an interface to launch your EDSL surveys as studies on Prolific, a platform for recruiting human participants for research studies.


How it works
------------

1. **Create a survey**: Use EDSL to create a survey, or use the :ref:`survey_builder` interface to build a survey interactively.
Run the survey with AI agents and models to generate responses.
See the :ref:`surveys` section for more details on creating surveys and accessing :ref:`results`.

2. **Post the survey to Coop:** Use the `push` method to add the survey to your Coop content:

.. code-block:: python

    survey.push(
        description = "A brief description of the survey", # optional
        alias = "my_survey", # optional, used to create a unique URL in addition to the Coop UUID URL
        visibility = "public", # optional, can also be"private" or "unlisted" (by default)
    )

This will return the Coop UUID of the survey, which you can use to access it later.

*Note:* Surveys created using :ref:`survey_builder` are automatically stored at Coop.

3. **Create a new project:** In the Coop interface, create a new project and select the survey you posted.

4. **Create a Prolific study:** Select the option to create a new study and fill in the study details:

   - **Study name** *(Shown to participants)*
   - **Description** *(Shown to participants)*
   - **Required number os participants:** Specify how many participants you want to recruit.
   - **Estimated completion time:** Provide an estimate of how long it will take participants to complete the survey.
   - **Participant payment amount:** Set the payment amount for participants.
   - **Participant allowlist:** Optionally, you can specify a list of Prolific IDs of participants who are allowed to take part in the study.
   - **Configure filters:** Optionally, you can set filters to target specific demographics or characteristics of participants (e.g., age, gender, ethnicity, languages, location, education, work status, etc.).
    
    *Note:* The **Study URL** will be generated automatically. 
    You can open it to view the web-based version of the survey that will be sent to participants.

    Click the **Create study** button to finalize the study creation.

5. **Launch the study:** Find the new study at your project dashboard and select the option to launch it.
Responses will automatically appear at your project dashboard where you can review and approve them.

6. **Access results:** You can combine the AI-generated responses with human responses using the `Results` class.
Copy the project UUID from the Coop interface and use it to access the results in your EDSL code (see example below).


Costs 
-----

Credits for launching Prolific studies are deducted from your Coop credits balance.
The total cost of a Prolific study is calculated based on the number of participants and the payment amount you set for each participant.
These costs are displayed in the Coop interface when you create the study, which include the Prolific platform fee and the payment to participants.
You can view your credits balance at your `Credits <https://www.expectedparrot.com/credits>`_ of your Coop account individual transactions at your `Transactions <https://www.expectedparrot.com/transactions>`_ page.



Example
-------


.. code-block:: python

    # Import modules from EDSL
    from edsl import (
        QuestionYesNo,
        QuestionNumerical,
        QuestionLinearScale,
        Survey,
        Agent,
        Model,
        Coop
    )

    # Create a survey with different question types
    q1 = QuestionYesNo(
        question_name="drive", 
        question_text="Do you drive?"
    )

    q2 = QuestionNumerical(
        question_name="count",
        question_text="How many vehicles do you currently own or lease?",
    )

    q3 = QuestionLinearScale(
        question_name="enjoy",
        question_text="On a scale from 1 to 10, how much do you enjoy driving?",
        question_options=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        option_labels={1: "Hate it", 10: "Love it"},
    )

    # Create a survey with the questions
    survey = Survey(questions=[q1, q2, q3])

    survey.push(
        description = "Survey on vehicle ownership", # optional, stored at Coop content page
        alias = "vehicle-ownership-survey", # optional, used to create a unique URL in addition to the Coop UUID URL
        visibility = "public", # optional, "public" makes it visible to all Coop users, defaults to "unlisted"
    )

    # Create an AI agent to respond to the survey
    agent = Agent(
        traits={
            "persona": "You are a middle-aged mom working on a software startup.",
            "location": "Massachusetts",
        }
    )

    # Select a language model to generate the responses
    model = Model("gemini-1.5-pro", service_name="google")

    # Run the survey with the AI agent and model
    llm_results = survey.by(agent).by(model).run()

    # Use the Coop class to access Prolific results
    coop = Coop()

    # Copy the project UUID from the Coop interface
    prolific_results = coop.get_project_human_responses("<your_project_uuid>")

    # Combine AI and human results
    combined_results = prolific_results + llm_results  

    # Print the combined results
    combined_results.select("agent_name", "drive", "count", "enjoy")


Learn more about methods for working with results in the :ref:`results` section.


*Please reach out to us if you have any questions or feature requests!
You can post a message at our Discord channel or send us an email at info@expectedparrot.com*