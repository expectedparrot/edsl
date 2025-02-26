
class Humanize:
    """
    This is to construct the datastrture that will get send to coop to render the question for users. 

    [ ] Deal with question_options 
    [ ] Deal with files (FileStore objects)
    [ ] Render text w/ prior answers, scenarios, etc. 
    [ ] Dealt with instructions  


    Notes:
    Could the options have files? 
    """

    def __init__(
        self,
        question: "QuestionBase",
        scenario: "Scenario",
        prior_answers_dict: dict,
        agent: "Agent",
    ):
        self.scenario = scenario
        self.question = question.copy() # make a copy so it can be modified
        self.prior_answers_dict = prior_answers_dict
        self.agent = agent

        self.data = self.question.data

        self.extracted_question_options = self.question._extract_question_options(self.scenario, self.prior_answers_dict)

    def _deal_with_question_options(self) -> None:
        """This is supposed to deal with cases where the question_option is a jinja2 template string.
        
        It modifies the question options. 
        """
        if self.extracted_question_options != self.data.get("question_options"):
            self.question.question_options = self.extracted_question_options  # replace the question options with the extracted question options
        else:
            pass

    def _file_store_html_snippets(self) -> dict:
        """Deal with file keys in the question_text and question_options
        
        Each file key will be replaced with an html snippet of the file. 
        The files will also be sent to coop to render the file. 
        """
        # deals with files (FileStore objects)
        file_keys = self.question._file_keys(self.scenario)
        return {key: self.scenario[key].html_snippet(file_path_root = "coop_media_store") for key in file_keys}

    @property
    def replacements_dict(self) -> dict:
        """This is the dictionary that will be used to render the question.
        
        TODO: This will also need agent traits. 
        
        """
        return {**self.prior_answers_dict, **self.scenario, **self._file_store_html_snippets()}

    def humanized_data(self) -> dict: 
        self._deal_with_question_options()
        return self.question.render(self.replacements_dict, return_dict=True)
    


if __name__ == "__main__":
    from edsl.questions import QuestionMultipleChoice
    from edsl.scenarios import Scenario
    from edsl.agents import Agent

    q = QuestionMultipleChoice(question_name="color", question_text="What is your favorite color?, {{ nickname }}", question_options=["red", "blue", "green"])
    scenario = Scenario({'nickname': 'John'})
    agent = Agent()
    humanize = Humanize(q, scenario, {}, agent)
    print(humanize.humanized_data())


    q = QuestionMultipleChoice(question_name="color", question_text="What is your favorite color?, {{ nickname}}", question_options="{{ options}}")
    scenario = Scenario({'nickname': 'John', 'options': ['red', 'blue', 'green']})
    agent = Agent()
    humanize = Humanize(q, scenario, {}, agent)
    print(humanize.humanized_data())


    q = QuestionMultipleChoice(question_name="color", question_text="What is your favorite color?, {{ nickname}}", question_options=["{{A}}", "{{B}}"])
    scenario = Scenario({'nickname': 'John', 'options': ['red', 'blue', 'green'], "A":"Sailing", "B":"Hiking"})
    agent = Agent()
    humanize = Humanize(q, scenario, {}, agent)
    print(humanize.humanized_data())

    q = QuestionMultipleChoice(question_name="color", question_text="What is your favorite color?, {{ nickname}}", question_options=["{{A}}", "{{B}}"])
    scenario = Scenario({'nickname': 'John', 'options': ['red', 'blue', 'green'], "A":"Sailing {{ boat_type}}", "B":"Hiking", 'boat_type':"Aero"})
    agent = Agent()
    humanize = Humanize(q, scenario, {}, agent)
    print(humanize.humanized_data())

    q = QuestionMultipleChoice(question_name="color", question_text="What is your favorite color?, {{ nickname}}", question_options="{{ options}}")
    scenario = Scenario({'nickname': 'John', 'options': ["{{A}}", "{{B}}"], "A":"Sailing {{ boat_type}}", "B":"Hiking", 'boat_type':"Aero"})
    agent = Agent()
    humanize = Humanize(q, scenario, {}, agent)
    print(humanize.humanized_data())

    from edsl.scenarios import FileStore
    s = Scenario({'cool_file':FileStore.example()})
    from edsl import QuestionFreeText
    q = QuestionFreeText(question_name="file_check", 
                         question_text="What do you think of {{ cool_file}}")
    humanize = Humanize(q, s, {}, agent)
    from edsl import Question
    q = Question(**humanize.humanized_data())

    snippets = humanize._file_store_html_snippets()
    print(snippets)

    



