.. _survey_builder:

Survey Builder
==============

Overview
--------

Survey Builder is a user-friendly, no-code application for launching surveys and gathering responses from human respondents and AI agents. 
It is fully integrated with EDSL and available at your Coop account, allowing you to seamlessly design questions and agents, and analyze, visualize and share your results.

.. See a `clickable demo <https://app.arcade.software/share/MbB0C3UDuZE6JLgB68FL>`_ on how to use it.

See all the :ref:`humanize` page for information about methods for generating web-based versions of your surveys and analyzing human responses at your workspace.

Features
--------

- **Survey creation**: Build customized surveys using a wide range of question types, including multiple choice, free text, linear scale, matrix, numerical and more.
- **AI agent design**: Create and configure AI agent personas to respond to your questions. 
- **Dynamic data integration**: Import data from Coop and other sources to dynamically parameterize your surveys.
- **Seamless deployment**: Easily launch surveys with both human and AI respondents.
- **Results analysis**: Leverage built-in tools to visualize and analyze responses, combining human and AI data for greater insights.
- **Team collaboration**: Share surveys, agents, results and projects with your team with tools for streamlined sharing and collaboration.


Getting started 
---------------

1. Log into your Coop account
    Sign in or create an account `here <https://www.expectedparrot.com/login>`_.

2. Create a survey
    Choose whether to build a new survey or start a project using an existing survey from your Coop content.

3. Design AI agents
    Design AI agents with relevant personas to answer your survey questions. 
    Send a web-based version to human respondents.

4. Run the survey
    Launch your survey with LLMs and humans and collect responses.

5. Analyze results
    View and analyze survey responses at your account, and export data for further analysis.



Create a survey
^^^^^^^^^^^^^^^

`Log in <https://www.expectedparrot.com/login>`_ to your Coop account and navigate to the `Create <https://www.expectedparrot.com/create>`_ page.
Choose whether to build a survey from scratch or import an existing survey to use in your project:

.. image:: static/sb01.png
   :alt: Create page options
   :align: center
   :width: 100%


.. raw:: html

   <br>


At the survey builder interface you can add and edit questions, configure survey logic, and save the survey as a new project:

.. image:: static/sb02.png
   :alt: Create project
   :align: center
   :width: 100%

.. raw:: html

   <br>


Your new project page has options for generating a web-based version of the survey, editing the survey, running the survey with AI agents, and launching studies with human participants.
AI and human responses will automatically appear at your dashboard where you can compare and export them:

.. image:: static/sb03.png
   :alt: Project page
   :align: center
   :width: 100%


.. raw:: html

    <br>



Human responses
^^^^^^^^^^^^^^^

Click the *Web survey* button to open a web-based version of your survey.
Share the URL with your target audience to collect responses.
Recorded responses will be appear in the *Human responses* tab where you can view and analyze them.


Agent responses 
^^^^^^^^^^^^^^^

To run the survey with AI agents you first need to create agents.
Click the *Agent list* button at the `Create <https://www.expectedparrot.com/create>`_ page to choose whether to use the interface to create agents or to import agents from a CSV file:

.. image:: static/sb04.png
   :alt: Create agents
   :align: center
   :width: 100%

.. raw:: html

    <br>


Click the *Create agent list* button to save the agents to your `Content <https://www.expectedparrot.com/content>`_. 
You can edit the agents at any time.


Run the survey 
^^^^^^^^^^^^^^

To run the survey with AI agents, click the *Run survey* button at the project page.
Tabs for adding agents and scenarios and selecting models to use will be displayed.

You can add agents to the survey by clicking the *Add agents* button.
Information about the selected agents will be displayed:

.. image:: static/sb05.png
   :alt: Run survey add agents interface
   :align: center
   :width: 100%

.. raw:: html

    <br>


If your survey questions use :ref:`scenarios`, select the *Add scenarios* tab to either construct or import scenarios for a CSV file (the same steps for adding agents).

Select the *Add models* tab to choose the language models to use for generating responses.
If you do not select any models the default model will be used (currently *gpt-4o-mini*).

Then select the *Run* tab to preview the components of the survey and click the *Run* button to start the survey.
Refresh your project dashboard to view the responses that are generated, and select columns of the results to display and analyze.
You can also export the results for further analysis.

*Please let us know if you have any questions or suggestions for improving the survey builder!*