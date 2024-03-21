Frequently Asked Questions
==========================

Have a question that isn’t covered here? Please let us know!

Post a question at our Discord server

Send us an email: info@expectedparrot.com

.. code:: 

    # EDSL should be automatically installed when you run this notebook. If not, run the following command:
    # ! pip install edsl

Can I see a progress bar while a survey is running?
---------------------------------------------------

Add ``progress_bar = True`` to the ``.run()`` method to display a
progress bar while a survey is running:

.. code:: 

    from edsl.questions import QuestionMultipleChoice
    
    q = QuestionMultipleChoice(
        question_name = "question_1",
        question_text = "What is your favorite color?",
        question_options = ["Red", "Blue", "Green", "Yellow"],
    )
    
    q.run(progress_bar = True)



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace"><span style="font-style: italic">               Job Status               </span>
    
     <span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Key                        </span> <span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Value   </span> 
     ────────────────────────────────────── 
     <span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> </span><span style="color: #bf7f7f; text-decoration-color: #bf7f7f; font-weight: bold">Task status               </span><span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> </span>           
     <span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Total interviews requested </span>  1        
     <span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Completed interviews       </span>  1        
     <span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Percent complete           </span>  100.00%  
     <span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>           
    
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace"></pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">Result <span style="color: #008080; text-decoration-color: #008080; font-weight: bold">0</span>
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace"><span style="font-style: italic">                                                      Result                                                       </span>
    ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="font-weight: bold"> Attribute          </span>┃<span style="font-weight: bold"> Value                                                                                      </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="font-weight: bold"> agent              </span>│ <span style="font-style: italic">                                     Agent Attributes                                     </span> │
    │<span style="font-weight: bold">                    </span>│ ┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
    │<span style="font-weight: bold">                    </span>│ ┃<span style="font-weight: bold"> Attribute               </span>┃<span style="font-weight: bold"> Value                                                        </span>┃ │
    │<span style="font-weight: bold">                    </span>│ ┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> _name                   </span>│<span style="font-weight: bold"> None                                                         </span>│ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> _traits                 </span>│<span style="font-weight: bold"> {}                                                           </span>│ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> _codebook               </span>│<span style="font-weight: bold"> {}                                                           </span>│ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> _instruction            </span>│<span style="font-weight: bold"> 'You are answering questions as if you were a human. Do not  </span>│ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                         </span>│<span style="font-weight: bold"> break character.'                                            </span>│ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> set_instructions        </span>│<span style="font-weight: bold"> False                                                        </span>│ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> dynamic_traits_function </span>│<span style="font-weight: bold"> None                                                         </span>│ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> current_question        </span>│<span style="font-weight: bold"> QuestionMultipleChoice(question_text = 'What is your         </span>│ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                         </span>│<span style="font-weight: bold"> favorite color?', question_options = ['Red', 'Blue',         </span>│ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                         </span>│<span style="font-weight: bold"> 'Green', 'Yellow'], question_name = 'question_1',            </span>│ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                         </span>│<span style="font-weight: bold"> short_names_dict = {})                                       </span>│ │
    │<span style="font-weight: bold">                    </span>│ └─────────────────────────┴──────────────────────────────────────────────────────────────┘ │
    │<span style="font-weight: bold"> scenario           </span>│ <span style="font-style: italic"> Scenario Attributes </span>                                                                      │
    │<span style="font-weight: bold">                    </span>│ ┏━━━━━━━━━━━┳━━━━━━━┓                                                                      │
    │<span style="font-weight: bold">                    </span>│ ┃<span style="font-weight: bold"> Attribute </span>┃<span style="font-weight: bold"> Value </span>┃                                                                      │
    │<span style="font-weight: bold">                    </span>│ ┡━━━━━━━━━━━╇━━━━━━━┩                                                                      │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> data      </span>│<span style="font-weight: bold"> {}    </span>│                                                                      │
    │<span style="font-weight: bold">                    </span>│ └───────────┴───────┘                                                                      │
    │<span style="font-weight: bold"> model              </span>│ <span style="font-style: italic">                                      Language Model                                      </span> │
    │<span style="font-weight: bold">                    </span>│ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
    │<span style="font-weight: bold">                    </span>│ ┃<span style="font-weight: bold"> Attribute                   </span>┃<span style="font-weight: bold"> Value                                                    </span>┃ │
    │<span style="font-weight: bold">                    </span>│ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> model                       </span>│ 'gpt-3.5-turbo'                                          │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> parameters                  </span>│ {'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1,     │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                             </span>│ 'frequency_penalty': 0, 'presence_penalty': 0,           │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                             </span>│ 'use_cache': True}                                       │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> temperature                 </span>│ 0.5                                                      │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> max_tokens                  </span>│ 1000                                                     │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> top_p                       </span>│ 1                                                        │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> frequency_penalty           </span>│ 0                                                        │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> presence_penalty            </span>│ 0                                                        │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> use_cache                   </span>│ True                                                     │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> api_queue                   </span>│ &lt;queue.Queue object at 0x7f4b67508610&gt;                   │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> crud                        </span>│ &lt;edsl.data.crud.CRUDOperations object at 0x7f4b7508b1f0&gt; │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> _LanguageModel__rate_limits </span>│ {'rpm': 10000, 'tpm': 2000000}                           │ │
    │<span style="font-weight: bold">                    </span>│ └─────────────────────────────┴──────────────────────────────────────────────────────────┘ │
    │<span style="font-weight: bold"> iteration          </span>│ 0                                                                                          │
    │<span style="font-weight: bold"> answer             </span>│ <span style="font-style: italic">                                       Answers                                       </span>      │
    │<span style="font-weight: bold">                    </span>│ ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓      │
    │<span style="font-weight: bold">                    </span>│ ┃<span style="font-weight: bold"> Attribute          </span>┃<span style="font-weight: bold"> Value                                                        </span>┃      │
    │<span style="font-weight: bold">                    </span>│ ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩      │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> question_1         </span>│ 'Blue'                                                       │      │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> question_1_comment </span>│ 'Blue is my favorite color. I find it calming and peaceful.' │      │
    │<span style="font-weight: bold">                    </span>│ └────────────────────┴──────────────────────────────────────────────────────────────┘      │
    │<span style="font-weight: bold"> prompt             </span>│ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
    │<span style="font-weight: bold">                    </span>│ ┃<span style="font-weight: bold"> Attribute                </span>┃<span style="font-weight: bold"> Value                                                       </span>┃ │
    │<span style="font-weight: bold">                    </span>│ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> question_1_user_prompt   </span>│ {'text': 'You are being asked the following question: What  │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                          </span>│ is your favorite color?\nThe options are\n\n0: Red\n\n1:    │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                          </span>│ Blue\n\n2: Green\n\n3: Yellow\n\nReturn a valid JSON        │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                          </span>│ formatted like this, selecting only the number of the       │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                          </span>│ option:\n{"answer": &lt;put answer code here&gt;, "comment":      │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                          </span>│ "&lt;put explanation here&gt;"}\nOnly 1 option may be selected.', │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                          </span>│ 'class_name': 'MultipleChoiceTurbo'}                        │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> question_1_system_prompt </span>│ {'text': 'You are answering questions as if you were a      │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                          </span>│ human. Do not break character. You are an agent with the    │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                          </span>│ following persona:\n{}', 'class_name': 'AgentInstruction'}  │ │
    │<span style="font-weight: bold">                    </span>│ └──────────────────────────┴─────────────────────────────────────────────────────────────┘ │
    │<span style="font-weight: bold"> raw_model_response </span>│ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
    │<span style="font-weight: bold">                    </span>│ ┃<span style="font-weight: bold"> Attribute                     </span>┃<span style="font-weight: bold"> Value                                                  </span>┃ │
    │<span style="font-weight: bold">                    </span>│ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold"> question_1_raw_model_response </span>│ {'id': 'chatcmpl-9080T8zAVvlOUcX0IjJ2R1cG0zSUM',       │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ 'choices': [{'finish_reason': 'stop', 'index': 0,      │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ 'logprobs': None, 'message': {'content': '{"answer":   │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ 1, "comment": "Blue is my favorite color. I find it    │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ calming and peaceful."}', 'role': 'assistant',         │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ 'function_call': None, 'tool_calls': None}}],          │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ 'created': 1709817805, 'model': 'gpt-3.5-turbo-0125',  │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ 'object': 'chat.completion', 'system_fingerprint':     │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ 'fp_b9d4cef803', 'usage': {'completion_tokens': 24,    │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ 'prompt_tokens': 113, 'total_tokens': 137,             │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ 'cached_response': None, 'elapsed_time':               │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ 1.1728191375732422, 'timestamp': 1709817806.407605},   │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ 'elapsed_time': 1.1728191375732422, 'timestamp':       │ │
    │<span style="font-weight: bold">                    </span>│ │<span style="font-weight: bold">                               </span>│ 1709817806.407605, 'cached_response': False}           │ │
    │<span style="font-weight: bold">                    </span>│ └───────────────────────────────┴────────────────────────────────────────────────────────┘ │
    └────────────────────┴────────────────────────────────────────────────────────────────────────────────────────────┘
    </pre>





.. parsed-literal::

    Result 0
                                                          Result                                                       
    ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Attribute          ┃ Value                                                                                      ┃
    ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ agent              │                                      Agent Attributes                                      │
    │                    │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
    │                    │ ┃ Attribute               ┃ Value                                                        ┃ │
    │                    │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
    │                    │ │ _name                   │ None                                                         │ │
    │                    │ │ _traits                 │ {}                                                           │ │
    │                    │ │ _codebook               │ {}                                                           │ │
    │                    │ │ _instruction            │ 'You are answering questions as if you were a human. Do not  │ │
    │                    │ │                         │ break character.'                                            │ │
    │                    │ │ set_instructions        │ False                                                        │ │
    │                    │ │ dynamic_traits_function │ None                                                         │ │
    │                    │ │ current_question        │ QuestionMultipleChoice(question_text = 'What is your         │ │
    │                    │ │                         │ favorite color?', question_options = ['Red', 'Blue',         │ │
    │                    │ │                         │ 'Green', 'Yellow'], question_name = 'question_1',            │ │
    │                    │ │                         │ short_names_dict = {})                                       │ │
    │                    │ └─────────────────────────┴──────────────────────────────────────────────────────────────┘ │
    │ scenario           │  Scenario Attributes                                                                       │
    │                    │ ┏━━━━━━━━━━━┳━━━━━━━┓                                                                      │
    │                    │ ┃ Attribute ┃ Value ┃                                                                      │
    │                    │ ┡━━━━━━━━━━━╇━━━━━━━┩                                                                      │
    │                    │ │ data      │ {}    │                                                                      │
    │                    │ └───────────┴───────┘                                                                      │
    │ model              │                                       Language Model                                       │
    │                    │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
    │                    │ ┃ Attribute                   ┃ Value                                                    ┃ │
    │                    │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
    │                    │ │ model                       │ 'gpt-3.5-turbo'                                          │ │
    │                    │ │ parameters                  │ {'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1,     │ │
    │                    │ │                             │ 'frequency_penalty': 0, 'presence_penalty': 0,           │ │
    │                    │ │                             │ 'use_cache': True}                                       │ │
    │                    │ │ temperature                 │ 0.5                                                      │ │
    │                    │ │ max_tokens                  │ 1000                                                     │ │
    │                    │ │ top_p                       │ 1                                                        │ │
    │                    │ │ frequency_penalty           │ 0                                                        │ │
    │                    │ │ presence_penalty            │ 0                                                        │ │
    │                    │ │ use_cache                   │ True                                                     │ │
    │                    │ │ api_queue                   │ <queue.Queue object at 0x7f4b67508610>                   │ │
    │                    │ │ crud                        │ <edsl.data.crud.CRUDOperations object at 0x7f4b7508b1f0> │ │
    │                    │ │ _LanguageModel__rate_limits │ {'rpm': 10000, 'tpm': 2000000}                           │ │
    │                    │ └─────────────────────────────┴──────────────────────────────────────────────────────────┘ │
    │ iteration          │ 0                                                                                          │
    │ answer             │                                        Answers                                             │
    │                    │ ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓      │
    │                    │ ┃ Attribute          ┃ Value                                                        ┃      │
    │                    │ ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩      │
    │                    │ │ question_1         │ 'Blue'                                                       │      │
    │                    │ │ question_1_comment │ 'Blue is my favorite color. I find it calming and peaceful.' │      │
    │                    │ └────────────────────┴──────────────────────────────────────────────────────────────┘      │
    │ prompt             │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
    │                    │ ┃ Attribute                ┃ Value                                                       ┃ │
    │                    │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
    │                    │ │ question_1_user_prompt   │ {'text': 'You are being asked the following question: What  │ │
    │                    │ │                          │ is your favorite color?\nThe options are\n\n0: Red\n\n1:    │ │
    │                    │ │                          │ Blue\n\n2: Green\n\n3: Yellow\n\nReturn a valid JSON        │ │
    │                    │ │                          │ formatted like this, selecting only the number of the       │ │
    │                    │ │                          │ option:\n{"answer": <put answer code here>, "comment":      │ │
    │                    │ │                          │ "<put explanation here>"}\nOnly 1 option may be selected.', │ │
    │                    │ │                          │ 'class_name': 'MultipleChoiceTurbo'}                        │ │
    │                    │ │ question_1_system_prompt │ {'text': 'You are answering questions as if you were a      │ │
    │                    │ │                          │ human. Do not break character. You are an agent with the    │ │
    │                    │ │                          │ following persona:\n{}', 'class_name': 'AgentInstruction'}  │ │
    │                    │ └──────────────────────────┴─────────────────────────────────────────────────────────────┘ │
    │ raw_model_response │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
    │                    │ ┃ Attribute                     ┃ Value                                                  ┃ │
    │                    │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
    │                    │ │ question_1_raw_model_response │ {'id': 'chatcmpl-9080T8zAVvlOUcX0IjJ2R1cG0zSUM',       │ │
    │                    │ │                               │ 'choices': [{'finish_reason': 'stop', 'index': 0,      │ │
    │                    │ │                               │ 'logprobs': None, 'message': {'content': '{"answer":   │ │
    │                    │ │                               │ 1, "comment": "Blue is my favorite color. I find it    │ │
    │                    │ │                               │ calming and peaceful."}', 'role': 'assistant',         │ │
    │                    │ │                               │ 'function_call': None, 'tool_calls': None}}],          │ │
    │                    │ │                               │ 'created': 1709817805, 'model': 'gpt-3.5-turbo-0125',  │ │
    │                    │ │                               │ 'object': 'chat.completion', 'system_fingerprint':     │ │
    │                    │ │                               │ 'fp_b9d4cef803', 'usage': {'completion_tokens': 24,    │ │
    │                    │ │                               │ 'prompt_tokens': 113, 'total_tokens': 137,             │ │
    │                    │ │                               │ 'cached_response': None, 'elapsed_time':               │ │
    │                    │ │                               │ 1.1728191375732422, 'timestamp': 1709817806.407605},   │ │
    │                    │ │                               │ 'elapsed_time': 1.1728191375732422, 'timestamp':       │ │
    │                    │ │                               │ 1709817806.407605, 'cached_response': False}           │ │
    │                    │ └───────────────────────────────┴────────────────────────────────────────────────────────┘ │
    └────────────────────┴────────────────────────────────────────────────────────────────────────────────────────────┘



How does the ``.by()`` method work?
-----------------------------------

Use the ``.by()`` method to add any optional components to your question
or survey before running it (with the ``.run()`` method, which always
comes last). For example, here we administer a single question with a
single scenario to a single agent with a single specified model:

::

   q = QuestionMultipleChoice(...)
   scenario = Scenario(...) 
   agent = Agent(...)
   model = Model(...)

   results = q.by(scenario).by(agent).by(model).run()

If multiple objects of the same type are to be used (more than one
Model, Agent or Scenario), they should be put in a list and passed to
the same ``.by()`` clause:

::

   scenarios = [Scenario(...), Scenario(...)] 
   agents = [Agent(...), Agent(...)]
   models = [Model(...), Model(...)]

   results = q.by(scenarios).by(agents).by(models).run()

The ``.by()`` method is applied identically when running a survey of
questions as a single question:

::

   survey = Survey(questions = [q1, q2, q3])

   results = survey.by(scenarios).by(agents).by(models).run()

\**\* Note that the order of the ``.by()`` clauses does not matter.
However, if a question is going to be added to a survey, the ``.by()``
method should be appended to the survey instead of the individual
question (e.g., if a question has scenarios, ``.by(scenarios)`` should
be appended to the survey after the question is added to it). \**\*

How do I access survey results?
-------------------------------

Edsl has a variety of built-in method for accessing ``Results`` objects
generated when you run a survey. Some of these are listed below. You can
also see more details in this notebook: Tutorial - Exploring Your
Results

Start by using the ``.columns`` method to get a list of all the columns
in your results:

::

   results.columns

The list will include all the fields with information about the models
used (temperature, etc.), user and system prompts, any agent personas
and question scenarios, and responses to the questions.

Print
~~~~~

Use the ``.select()`` method to select specific columns from your
results and then print them in a table with the ``.print()`` method:

::

   results.select("agent.persona", "answer.question_1").print()

SQL
~~~

Query your results as a data table with the ``.sql()`` method:

::

   results.sql("select * from self", shape="wide")

The method takes a SQL query string and a shape (wide or long).

Dataframes
~~~~~~~~~~

Turn your results into a dataframes with the ``.to_pandas()`` method.

::

   results.to_pandas()

Select columns as you would with any dataframe:

::

   results.to_pandas()[["column_a", "column_b"]]

What is the default LLM and how do I change it?
-----------------------------------------------

The default LLM is GPT-4. You can verify this by running a ``Model``
object with no parameters:

.. code:: 

    from edsl import Model
    
    Model()


.. parsed-literal::

    No model name provided, using default model: gpt-4-1106-preview




.. parsed-literal::

    LanguageModelOpenAIFour(model = 'gpt-4-1106-preview', parameters={'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, 'frequency_penalty': 0, 'presence_penalty': 0, 'use_cache': True})



You can see all of the available models by running
``Model.available()``:

.. code:: 

    Model.available()




.. parsed-literal::

    ['gpt-3.5-turbo',
     'gpt-4-1106-preview',
     'gemini_pro',
     'llama-2-13b-chat-hf',
     'llama-2-70b-chat-hf',
     'mixtral-8x7B-instruct-v0.1']



You can specify the models that you want to use in simulating results by
specifying the model names in the ``Model`` object:

.. code:: 

    models = [Model(m) for m in ["gpt-3.5-turbo", "gpt-4-1106-preview"]]

How do I add skip logic to my survey?
-------------------------------------

Apply skip/stop logic to your survey by appending an expression with the
``.add_stop_rule`` method. See this notebook for an example: Skip Logic.
Here’s another one:

.. code:: 

    # Add skip/stop logic to your survey
    
    from edsl.questions import QuestionYesNo, QuestionFreeText
    from edsl import Survey, Agent
    
    q_exercise = QuestionYesNo(
        question_name = "exercise",
        question_text = "Do you enjoy exercising?"
    )
    
    q_favorites = QuestionFreeText(
        question_name = "favorites",
        question_text = "What are your favorite ways to exercise?"
    )
    
    survey = Survey(questions = [q_exercise, q_favorites])
    
    # Append the stop rule to your survey
    survey.add_stop_rule("exercise","exercise == 'No'")
    
    # Create some personas that will trigger the logic
    agents = [Agent(traits={"persona":p}) for p in ["Athlete", "Couch potato"]]
    
    results = survey.by(agents).run()
    results.select("exercise", "favorites").print()


.. parsed-literal::

    WARNING: At least one question in the survey was not answered.
    
    Task `exercise` failed with `TypeError`:`'>' not supported between instances of 'EndOfSurveyParent' and 'int'`.
    Task `favorites` failed with `InterviewErrorPriorTaskCanceled`:`Required tasks failed for favorites`.



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer    </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                                                                              </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .exercise </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .favorites                                                                                          </span>┃
    ┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Yes       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite ways to exercise include weightlifting, running, and playing team sports like           </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">           </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> basketball and soccer. I also enjoy mixing it up with yoga and swimming for some variety in my      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">           </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> routine.                                                                                            </span>│
    ├───────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> No        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> None                                                                                                </span>│
    └───────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────┘
    </pre>



How do I seed a question with information from the response to another question?
--------------------------------------------------------------------------------

Survey questions are administered asynchronously by default to save time
in generating results. If you want to include the response to a question
in a follow-on question there are 2 ways to do this.

Method 1: Using the ``.add_targeted_memory()`` method
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: 

    from edsl.questions import QuestionYesNo, QuestionFreeText
    from edsl import Survey, Agent
    
    q_exercise = QuestionYesNo(
        question_name = "exercise",
        question_text = "Do you enjoy exercising?"
    )
    
    q_reasons = QuestionFreeText(
        question_name = "reasons",
        question_text = "What are your reasons?"
    )
    
    survey = Survey(questions = [q_exercise, q_reasons])
    survey.add_targeted_memory(q_reasons, q_exercise)
    
    # Create some personas that will answering differently
    agents = [Agent(traits={"persona":p}) for p in ["Athlete", "Couch potato"]]
    
    results = survey.by(agents).run()
    
    # Inspect the prompts to see how the `_user_prompt` has been modified for the second question:
    # "You are being asked ... Before the question you are now answering, you already answered the following question(s): ..."
    results.select("prompt.*").print()



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> prompt                     </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> prompt                    </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> prompt                     </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> prompt                    </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .reasons_system_prompt     </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .reasons_user_prompt      </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .exercise_system_prompt    </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .exercise_user_prompt     </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': "You are          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': 'You are being   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': "You are          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': 'You are being   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answering questions as if  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> asked the following       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answering questions as if  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> asked the following       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> you were a human. Do not   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> question: What are your   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> you were a human. Do not   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> question: Do you enjoy    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> break character. You are   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> reasons?\nReturn a valid  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> break character. You are   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> exercising?\nThe options  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> an agent with the          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> JSON formatted like       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> an agent with the          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> are\n\n0: Yes\n\n1:       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> following                  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> this:\n{"answer": "&lt;put   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> following                  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> No\n\nReturn a valid JSON </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> persona:\n{'persona':      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> free text answer          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> persona:\n{'persona':      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> formatted like this,      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'Athlete'}", 'class_name': </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> here&gt;"}\n        Before   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'Athlete'}", 'class_name': </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> selecting only the number </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'AgentInstruction'}        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the question you are now  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'AgentInstruction'}        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> of the                    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answering, you already    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> option:\n{"answer": &lt;put  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answered the following    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answer code here&gt;,        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> question(s):\n            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> "comment": "&lt;put          </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> \tQuestion: Do you enjoy  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> explanation here&gt;"}\nOnly </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> exercising?\n\tAnswer:    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1 option may be           </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Yes\n', 'class_name':     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> selected.', 'class_name': </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'FreeText'}               </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'YesNo'}                  </span>│
    ├────────────────────────────┼───────────────────────────┼────────────────────────────┼───────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': "You are          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': 'You are being   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': "You are          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': 'You are being   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answering questions as if  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> asked the following       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answering questions as if  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> asked the following       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> you were a human. Do not   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> question: What are your   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> you were a human. Do not   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> question: Do you enjoy    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> break character. You are   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> reasons?\nReturn a valid  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> break character. You are   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> exercising?\nThe options  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> an agent with the          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> JSON formatted like       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> an agent with the          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> are\n\n0: Yes\n\n1:       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> following                  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> this:\n{"answer": "&lt;put   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> following                  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> No\n\nReturn a valid JSON </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> persona:\n{'persona':      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> free text answer          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> persona:\n{'persona':      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> formatted like this,      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'Couch potato'}",          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> here&gt;"}\n        Before   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'Couch potato'}",          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> selecting only the number </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'class_name':              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the question you are now  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'class_name':              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> of the                    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'AgentInstruction'}        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answering, you already    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'AgentInstruction'}        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> option:\n{"answer": &lt;put  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answered the following    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answer code here&gt;,        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> question(s):\n            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> "comment": "&lt;put          </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> \tQuestion: Do you enjoy  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> explanation here&gt;"}\nOnly </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> exercising?\n\tAnswer:    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1 option may be           </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> No\n', 'class_name':      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> selected.', 'class_name': </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'FreeText'}               </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'YesNo'}                  </span>│
    └────────────────────────────┴───────────────────────────┴────────────────────────────┴───────────────────────────┘
    </pre>



Method 2: Using the ``compose_questions()`` method
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: 

    from edsl.questions.compose_questions import compose_questions
    from edsl.questions import QuestionYesNo, QuestionFreeText
    from edsl import Survey, Agent
    
    q_exercise = QuestionYesNo(
        question_name = "exercise",
        question_text = "Do you enjoy exercising?"
    )
    
    q_reasons = QuestionFreeText(
        question_name = "reasons",
        question_text = "You were previously asked: " + q_exercise.question_text 
        + " You responded: {{exercise}}. What are your reasons?"
    )
    
    q_exercise_reasons = compose_questions(q_exercise, q_reasons)
    
    survey = Survey(questions = [q_exercise, q_exercise_reasons])
    
    # Create some personas that will answering differently
    agents = [Agent(traits={"persona":p}) for p in ["Athlete", "Couch potato"]]
    
    results = survey.by(agents).run()

.. code:: 

    results.columns




.. parsed-literal::

    ['agent.agent_name',
     'agent.persona',
     'answer.exercise',
     'answer.exercise_comment',
     'answer.exercise_reasons',
     'answer.exercise_reasons_comment',
     'model.frequency_penalty',
     'model.max_tokens',
     'model.model',
     'model.presence_penalty',
     'model.temperature',
     'model.top_p',
     'model.use_cache',
     'prompt.exercise_reasons_system_prompt',
     'prompt.exercise_reasons_user_prompt',
     'prompt.exercise_system_prompt',
     'prompt.exercise_user_prompt']



.. code:: 

    results.select("persona", "exercise", "exercise_reasons").print()



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> agent        </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer    </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                                                               </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .persona     </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .exercise </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .exercise_reasons                                                                    </span>┃
    ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Athlete      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Yes       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'answer': {'answer.reasons': ['I enjoy exercising because it helps me stay fit,     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">           </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> boosts my mood, and gives me a sense of accomplishment.']}, 'comment': None}         </span>│
    ├──────────────┼───────────┼──────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Couch potato </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> No        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'answer': {'answer.reasons': ['I find exercising to be tiring and boring. I prefer  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">           </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> to relax on the couch and watch TV instead.']}, 'comment': None}                     </span>│
    └──────────────┴───────────┴──────────────────────────────────────────────────────────────────────────────────────┘
    </pre>



.. code:: 

    (results
    .select("persona", "exercise", "exercise_reasons")
    .print(pretty_labels={
        "agent.persona":"Persona", 
        "answer.exercise":q_exercise.question_text, 
        "answer.exercise_reasons":q_reasons.question_text})
    )



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold">              </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold">                          </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> You were previously asked: Do you enjoy exercising? You responded:    </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold">              </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold">                          </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> {{exercise}}                                                          </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Persona      </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Do you enjoy exercising? </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> . What are your reasons?                                              </span>┃
    ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Athlete      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Yes                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'answer': {'answer.reasons': ['I enjoy exercising because it helps   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> me stay fit, boosts my mood, and gives me a sense of                  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> accomplishment.']}, 'comment': None}                                  </span>│
    ├──────────────┼──────────────────────────┼───────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Couch potato </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> No                       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'answer': {'answer.reasons': ['I find exercising to be tiring and    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> boring. I prefer to relax on the couch and watch TV instead.']},      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'comment': None}                                                      </span>│
    └──────────────┴──────────────────────────┴───────────────────────────────────────────────────────────────────────┘
    </pre>



We can also do this with a parameterized initial question:

.. code:: 

    from edsl import Scenario
    
    q_exercise = QuestionYesNo(
        question_name = "exercise",
        question_text = "Do you enjoy {{sport}}?"
    )
    
    q_reasons = QuestionFreeText(
        question_name = "reasons",
        question_text = "You were previously asked: " + q_exercise.question_text 
        + " You responded: {{exercise}}. What are your reasons?"
    )
    
    q_exercise_reasons = compose_questions(q_exercise, q_reasons)
    
    survey = Survey(questions = [q_exercise, q_exercise_reasons])
    
    results = survey.by(Scenario({"sport":"soccer"})).by(agents).run()
    
    results.select("persona", "scenario.sport", "exercise", "exercise_reasons").print()



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> agent        </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> scenario </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer    </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                                                    </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .persona     </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .sport   </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .exercise </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .exercise_reasons                                                         </span>┃
    ┡━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Athlete      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> soccer   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Yes       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'answer': {'answer.reasons': ["I enjoy soccer because it allows me to    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">           </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> stay active, work on my agility and coordination, and compete as part of  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">           </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a team. It's a great way to stay fit and have fun at the same time."]},   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">           </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'comment': None}                                                          </span>│
    ├──────────────┼──────────┼───────────┼───────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Couch potato </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> soccer   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> No        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'answer': {'answer.reasons': ["I prefer to relax on the couch and watch  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">           </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> TV rather than participate in physical activities like soccer. It's just  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">           </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> not my cup of tea."]}, 'comment': None}                                   </span>│
    └──────────────┴──────────┴───────────┴───────────────────────────────────────────────────────────────────────────┘
    </pre>



How do I create new methods?
----------------------------

You can create new methods for your workflows by constructing methods
that administer questions and handle the responses. This can be
especially useful when you want to perform a set of operations
repeatedly, similar to parameterizing questions. For example, we can
create a simple method for performing cognitive tesing on our question
texts:

.. code:: 

    def question_feedback(draft_text, model="gpt-3.5-turbo"):
    
        from edsl.questions import QuestionFreeText
        from edsl import Model, Agent, Scenario
    
        model = Model(model)
        agent = Agent(traits={"persona":"You are an expert in survey design."})
    
        q = QuestionFreeText(
            question_name = "feedback",
            question_text = """Consider the following survey question: {{draft_text}}
            Identify any problematic phrases with the question, and then provide an improved version of it.
            Explain why your improved version is better. Be specific."""
        )
    
        scenario = Scenario({"draft_text":draft_text})
    
        return q.by(scenario).by(agent).by(model).run().select("feedback").print()


.. code:: 

    question_feedback("What is the best place in the world?")



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                                                                                          </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .feedback                                                                                                       </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> The phrase 'best place in the world' is problematic because it is subjective and can vary greatly from person   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> to person. To improve the question, it would be better to ask 'What is your favorite travel destination and     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> why?' This revised question is better because it allows respondents to provide a specific answer based on their </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> personal preferences and experiences, rather than trying to determine a universally 'best' place.               </span>│
    └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
    </pre>



Created in Deepnote
