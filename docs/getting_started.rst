Getting Started
===============

To use EDSL, you need to install the package and choose how you want to access language models.
Please see links to sections below for more details on each step.


1. Installation
---------------
   
   Run the following command to install the EDSL package:

   .. code:: 

      pip show edsl


   If you have previously installed EDSL, you can update it with the following command:

   .. code:: 

      pip install --upgrade edsl
   

   See :ref:`installation` instructions for information. 
   If you are using EDSL with Google Colab, see the :ref:`colab_setup` section for special instructions.


2. Create a Coop account
------------------------

   `Creating an account <https://www.expectedparrot.com/login>`_ allows you to access the Expected Parrot server to create and share projects, and run surveys with any available models.
   Your account comes with free storage and credits for running surveys, and special features and collaboration tools.

   Navigate to the `Sign up / Login <https://www.expectedparrot.com/login>`_ page to create an account with an email address.
   See the :ref:`coop` section for more details on using Coop to create and share projects.


3. Manage API keys for language models
--------------------------------------

   EDSL works with hundreds of language models from popular service providers (Anthropic, Azure, Bedrock, DeepSeek, Google, Mistral, OpenAI, Together, etc.).
   You can use ESDL with any available models by providing your own API keys from service providers or by using an Expected Parrot API key to access all of them at once.
   See the `model pricing page <https://www.expectedparrot.com/getting-started/coop-pricing>`_ for details on current available models and prices.
   Your account comes with 100 free credits for running surveys with your Expected Parrot API key.
   You can purchase additional credits at the `Credits <https://www.expectedparrot.com/home/credits>`_ page of your account.
   (Using your own keys does not require credits; service providers will bill you directly for your usage.)
   
   To store your own keys, navigate to the `Keys <https://www.expectedparrot.com/home/keys>`_ page of your account and choose options for adding and prioritizing keys.
   You can also share keys with other users and manage their access:

   .. image:: static/ep_key.png
   :alt: View stored keys
   :align: center
   :width: 100%
   

   .. raw:: html

   <br>


   See the :ref:`api_keys` section for more details and options for managing keys.


4. Choose where to run surveys
------------------------------

   You can use EDSL to run surveys locally on your own machine or remotely at the Expected Parrot server.
   To activate remote inference and caching for your surveys and results, navigate to the `Settings <https://www.expectedparrot.com/home/settings>`_ page of your account and toggle on the relevant options.
   Your Expected Parrot API key is automatically stored at your `Keys <https://www.expectedparrot.com/home/keys>`_ page and is used by default to run surveys at the Expected Parrot server unless you have prioritized other keys:

   .. image:: static/settings.png
   :alt: Toggle on remote inference
   :align: center
   :width: 100%
   

   .. raw:: html

   <br>


   To run surveys locally you must provide your own keys from service providers.

   See the :ref:`remote_inference` and :ref:`remote_caching` sections for details on using remote inference and caching.


5. Run a survey
---------------

   Read the :ref:`starter_tutorial` and `download a notebook <https://www.expectedparrot.com/content/179b3a78-2505-4568-acd9-c09d18953288>`_ to create a survey and run it.
   See examples for many other use cases and `tips <https://docs.expectedparrot.com/en/latest/checklist.html>`_ on using EDSL effectively in the documentation.



Support
-------

If you have any questions or need help, please send a message to `info@expectedparrot.com`.
You can also `open at issue at GitHub <https://github.com/expectedparrot/edsl/issues/new?template=Blank+issue>`_ to report bugs or request new features.

Please also join our `Discord channel <https://discord.com/invite/mxAYkjfy9m>`_ to ask questions and chat with other users!
