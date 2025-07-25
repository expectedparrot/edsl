.. _prolific:

Prolific studies
================

EDSL allows you to launch surveys with human participants using Prolific, a platform for recruiting participants for research studies.
You can choose whether to create and manage Prolific studies directly in your EDSL code or interactivately at your Coop account, enabling you to gather human responses to your surveys alongside AI-generated responses.
The steps below outline both methods (code-based and interactive).
A clickable demo of interactive steps is available `here <https://www.expectedparrot.com/getting-started/build>`_, and example code below on this page is also available at a downloadable `notebook at Coop <https://www.expectedparrot.com/content/RobinHorton/coop-project-example>`_.

More information about the `humanize` method for generating a shareable web version of your survey for human respondents is available at the :ref:`humanize` page.
This method allows you to collect responses from your own respondents.
The responses can then be combined with AI-generated responses (and Prolific responses) for analysis.

*Please reach out to us if you have any questions or feature requests, or are interested in testing new features for validating AI responses with participants!
You can post a message at our Discord channel or send us an email at info@expectedparrot.com - thank you!*


How it works
------------

You can create a Prolific study for your EDSL survey from your workspace (in code) or from your account dashboard (interactively).
You can also choose whether to use your own Prolific account key or your Expected Parrot key (by default).


Code-based workflow
^^^^^^^^^^^^^^^^^^^

1. **Create a survey in a notebook**

Create a survey in EDSL:

   - Construct :ref:`questions` and pass them to :ref:`surveys` with desired logic.
   - Create AI :ref:`agents` with desired traits.
   - Specify :ref:`language_models` to generate responses.
   - Use the `run` method to administer a survey with desired agents and models.

This generates a formatted dataset of :ref:`results` that you can analyze with built-in methods.
The survey, agents and results are also automatically added to your Coop account, where you can access them interactively.

2. **Use** `humanize` **to generate a project and web surveys**

Use the `humanize` method to generate a `Project` for your survey and a shareable web version.
You can optionally pass a `project_name`, `survey_description` and `survey_alias` to customize the project details (see example below).

3. **Use** `Coop` **to launch Prolific studies**

Create a `Coop` client object to access your account.
Then use `Coop` methods to create a Prolific study for your survey and gather human responses:

    - `create_prolific_study`: Create a new study for the `project_uuid` and specify the study details (`name`, `description`, `num_participant`, `estimated_completion_time` (minutes), `participant_payment_cents`), and optional filters for targeting specific demographics and Prolific participants (IDs list).
    - `get_prolific_study`: Retrieve the study details for the `project_uuid` and `study_id`.
    - `list_prolific_filters`: Show all the available filters for targeting specific demographics and characteristics of participants. Then use the `find` method to inspect the available filters by `filter_id` and the `create_study_filter` method to create a filter for your study with the desired parameters.
    - `update_prolific_study`: Update the study with the filters.
    - `publish_prolific_study`: Publish the study and make it available for participants.
    - `get_prolific_study_responses`: Retrieve the responses from the study.
    - `approve_prolific_study_submission`: Approve the responses from the study.
    - `reject_prolific_study_submission`: Reject the responses from the study.

If you have also shared the web link with other respondents, you can gather all human responses using the `get_project_human_responses` method.


Interactive workflow
^^^^^^^^^^^^^^^^^^^^

1. **Create a survey project**

`Log in <https://www.expectedparrot.com/login>`_ to your account. 
Create a project for a saved survey at your **Projects** page or create a new survey and select *Run survey* to view options for running the survey with AI agents and language models, generate a web version of the survey, and launch Prolific studies with human participants.

2. **Create a Prolific study:** 

Select the **Run with humans** option and fill in the study details:

   - **Study name** *(Shown to participants)*
   - **Description** *(Shown to participants)*
   - **Required number of participants:** Specify how many participants you want to recruit.
   - **Estimated completion time:** Provide an estimate of how long it will take participants to complete the survey.
   - **Participant payment amount:** Set the payment amount for participants.
   - **Participant allowlist:** Optionally, you can specify a list of Prolific IDs of participants who are allowed to take part in the study.
   - **Configure filters:** Optionally, you can set filters to target specific demographics or characteristics of participants (e.g., age, gender, ethnicity, languages, location, education, work status, etc.).
    
*Note:* The **Study URL** will be generated automatically. 
You can open it to view the web version of the survey that will be sent to participants.
This is the same link displayed when you select the **Web survey** option at your project page (or when you use the `humanize` method in code).
You can also share this link with any other respondents on your own to gather their responses.

Click the **Create study** button to finalize the study creation.

3. **Launch the study** 

Find the new study at your project dashboard and select the option to launch it.
Responses will automatically appear at your project dashboard where you can review and approve them.

4. **Access results** 

Copy the project UUID and use it to access the participant responses in your EDSL code (see example below).


Example (code-based workflow)
-----------------------------

The example below demonstrates how to create a survey with different question types, run it with an AI agent and language model, and then gather human responses.

**Create and run a survey with AI agents and models:**

See the :ref:`questions`, :ref:`surveys`, :ref:`agents` and :ref:`language_models` sections for more details on each of these components.

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

    # Create an AI agent to respond to the survey
    agent = Agent(
        traits={
            "persona":"Middle-aged mom",
            "location":"Massachusetts",
        }
    )

    # Select a language model to generate the responses
    model = Model("gemini-1.5-pro", service_name="google")

    # Run the survey with the AI agent and model
    llm_results = survey.by(agent).by(model).run()

    # Inspect the results
    llm_results.select("persona", "location", "drive", "count", "enjoy")


Example output:

.. list-table::
  :header-rows: 1

  * - agent.persona
    - Middle-aged mom
  * - agent.location
    - Massachusetts
  * - answer.drive
    - Yes
  * - answer.count
    - 2
  * - answer.enjoy
    - 4


**Create a project and web version of the survey for human respondents:**

Use the `humanize` method to create a project for the survey and a web version that can be shared with respondents (your own and via Prolific):

.. code-block:: python

    # Generate a web version of the survey for human respondents
    project = survey.humanize(
        project_name = "Vehicle Ownership Survey",  # optional, defaults to the survey name
        survey_description = "A survey on vehicle ownership and driving habits.",  # optional
        survey_alias = "vehicle-ownership-survey"  # optional, used to create a unique URL in addition to the Coop UUID URL
    )

    # Inspect the project details
    project


Example output:

.. code-block:: text

    {'project_name': 'Vehicle Ownership Survey',
    'uuid': '369b1bdc-11d4-4d22-8eeb-d0fb9eddd3cc',
    'admin_url': 'https://www.expectedparrot.com/home/projects/369b1bdc-11d4-4d22-8eeb-d0fb9eddd3cc',
    'respondent_url': 'https://www.expectedparrot.com/respond/369b1bdc-11d4-4d22-8eeb-d0fb9eddd3cc'}


The `respondent_url` can be shared with any human respondents (it is the same link shared with Prolific participants).


**Create a study for the project to launch studies on Prolific:**

.. code-block:: python

    # Create a Coop instance
    from edsl import Coop
    coop = Coop()

    project_uuid = project["uuid"]

    study = coop.create_prolific_study(
        project_uuid=project_uuid,
        name="Vehicle Ownership Study",
        description="A study on vehicle ownership and driving habits.",
        num_participants=1,
        estimated_completion_time_minutes=1,  # in minutes
        participant_payment_cents=50,  # payment amount in cents
    )

    # Inspect the study details
    study


Example output:

.. code-block:: text

    {'study_id': '684307d08015cf8252ca77cf',
    'status': 'UNPUBLISHED',
    'admin_url': 'https://www.expectedparrot.com/home/projects/369b1bdc-11d4-4d22-8eeb-d0fb9eddd3cc/prolific-studies/684307d08015cf8252ca77cf',
    'respondent_url': 'https://www.expectedparrot.com/respond/369b1bdc-11d4-4d22-8eeb-d0fb9eddd3cc',
    'name': 'Vehicle Ownership Study',
    'description': 'A study on vehicle ownership and driving habits.',
    'num_participants': 1,
    'estimated_completion_time_minutes': 1,
    'participant_payment_cents': 50,
    'total_cost_cents': 71,
    'device_compatibility': ['desktop', 'mobile', 'tablet'],
    'peripheral_requirements': [],
    'filters': []}


Inspect the study details:

.. code-block:: python

    # Get the study details
    study_id = study["id"]

    coop.get_prolific_study(project_uuid, study_id)


Example output:

.. code-block:: text

    {'study_id': '684307d08015cf8252ca77cf',
    'status': 'UNPUBLISHED',
    'admin_url': 'https://www.expectedparrot.com/home/projects/369b1bdc-11d4-4d22-8eeb-d0fb9eddd3cc/prolific-studies/684307d08015cf8252ca77cf',
    'respondent_url': 'https://www.expectedparrot.com/respond/369b1bdc-11d4-4d22-8eeb-d0fb9eddd3cc',
    'name': 'Vehicle Ownership Study',
    'description': 'A study on vehicle ownership and driving habits.',
    'num_participants': 1,
    'estimated_completion_time_minutes': 1,
    'participant_payment_cents': 50,
    'total_cost_cents': 71,
    'device_compatibility': ['desktop', 'mobile', 'tablet'],
    'peripheral_requirements': [],
    'filters': []}


**Applying filters:**

You can select and apply filters for targeting specific demographics and characteristics of participants.
To see a list of available filters:

.. code-block:: python

    filters = coop.list_prolific_filters()

    filters


*See the notebook above for the full list of available filters.*
*Keys to filter on: 'range_filter_max', 'type', 'select_filter_num_options', 'select_filter_options', 'question', 'filter_id', 'title', 'range_filter_min'*


There are two types of filters available: select and range.
*Select* filters will have `select_filter_num_options` and `select_filter_options`:

.. code-block:: python

    filter_id = "current-country-of-residence"  # Example filter ID

    filters.find(filter_id)


(See notebook for output.)

*Range* filters will have `range_filter_min` and `range_filter_max`:

.. code-block:: python

    filter_id = "age"  # Example filter ID

    filters.find(filter_id)


(See notebook for output.)

Create a filter by passing the id and desired parameters (*note*: you can also do this when you create the study).
Example *range* filter:

.. code-block:: python

    # Create a filter for the study
    age_filter = filters.create_study_filter(
        filter_id="age",  # Example filter ID
        min=40,
        max=60
    )

    # Inspect the created filter
    age_filter


Output:

.. code-block:: text

    {'filter_id': 'age', 'selected_range': {'lower': 40, 'upper': 60}}


Example *select* filter:

.. code-block:: python

    # Create a filter for the study
    country_filter = filters.create_study_filter(
        filter_id="current-country-of-residence",  # Example filter ID
        values=["United States", "Canada"]
    )

    # Inspect the created filter
    country_filter


Output:

.. code-block:: text

    {'filter_id': 'current-country-of-residence', 'selected_values': ['1', '45']}


Update the study with the filter:

.. code-block:: python

    # Update the study with the filter
    coop.update_prolific_study(
        project_uuid=project_uuid,
        study_id=study_id,
        filters=[
            age_filter,
            country_filter
        ]  # List of filters to apply to the study
    )


Example output:

.. code-block:: text

    {'study_id': '684307d08015cf8252ca77cf',
    'status': 'UNPUBLISHED',
    'admin_url': 'https://www.expectedparrot.com/home/projects/369b1bdc-11d4-4d22-8eeb-d0fb9eddd3cc/prolific-studies/684307d08015cf8252ca77cf',
    'respondent_url': 'https://www.expectedparrot.com/respond/369b1bdc-11d4-4d22-8eeb-d0fb9eddd3cc',
    'name': 'Vehicle Ownership Study',
    'description': 'A study on vehicle ownership and driving habits.',
    'num_participants': 1,
    'estimated_completion_time_minutes': 1,
    'participant_payment_cents': 50,
    'total_cost_cents': 71,
    'device_compatibility': ['desktop', 'mobile', 'tablet'],
    'peripheral_requirements': [],
    'filters': [{'filter_id': 'age', 'min': 40, 'max': 60},
    {'filter_id': 'current-country-of-residence',
    'values': ['United States', 'Canada']}]}


**Publish the study:**
The above steps have created a draft study.
To make it available for participants (*note*: this consumes credits):

.. code-block:: python

    # Publish the study
    coop.publish_prolific_study(project_uuid, study_id)


**Retrieve the study responses:**
After the study is published and participants have completed it, you can retrieve the responses, together with the submission ID for each response, which you can use to approve or reject submissions:

.. code-block:: python

    # Get the responses from the study
    coop.get_prolific_study_responses(project_uuid, study_id)


Approve the responses from the study:

.. code-block:: python

    # Approve the responses from the study
    submission_id = "1234567890"  # Example submission ID
    coop.approve_prolific_study_submission(
        project_uuid=project_uuid,
        study_id=study_id,
        submission_id=submission_id
    )


Optionally, you can reject responses if needed:

.. code-block:: python

    # Reject the responses from the study
    submission_id = "1234567890"  # Example submission ID
    coop.reject_prolific_study_submission(
        project_uuid=project_uuid,
        study_id=study_id,
        submission_id=submission_id,
        reason="LOW_EFFORT",
        explanation="I think you may have used AI to complete this submission, as there are no personal thoughts or opinions expressed."
    )


**Gather all human responses:**
If you have also shared the web survey link with other respondents, you can gather all human responses from the project:

.. code-block:: python

    # Get human responses from the web survey link
    human_responses = coop.get_project_human_responses(project_uuid)

    # Inspect the human responses
    human_responses.select("drive", "count", "enjoy")


Combine the AI-generated results with the human responses:

.. code-block:: python

    # Combine results (you can add Results objects for the same survey)
    combined_results = llm_results + human_responses

    # Inspect the combined results
    combined_results.select("persona", "location", "drive", "count", "enjoy")



Costs 
-----

Credits for launching Prolific studies are deducted from your credits balance.
The total cost of a Prolific study is calculated based on the number of participants, the payment amount you set for each participant, and the Prolific platform fee for each response.
These costs are displayed at the project page when you create the study, which include the Prolific platform fee and the payment to participants.

You can view your credits balance at your `Credits <https://www.expectedparrot.com/credits>`_ of your account individual transactions at your `Transactions <https://www.expectedparrot.com/transactions>`_ page.



*Please reach out to us if you have any questions or feature requests!
You can post a message at our Discord channel or send us an email at info@expectedparrot.com*