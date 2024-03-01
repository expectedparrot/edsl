import json
import requests
from typing import Any, Optional, Type, Union
from edsl import CONFIG
from edsl.agents import Agent, AgentList
from edsl.questions import Question
from edsl.results import Results
from edsl.surveys import Survey


api_url = {
    "development": "http://127.0.0.1:8000",
    "production": "https://api.goemeritus.com",
}


class Coop:
    def __init__(self, api_key: str = None, run_mode: str = None) -> None:
        self.api_key = api_key or CONFIG.EMERITUS_API_KEY
        self.run_mode = run_mode or CONFIG.EDSL_RUN_MODE

    def __repr__(self):
        return f"Client(api_key='{self.api_key}', run_mode='{self.run_mode}')"

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    @property
    def url(self) -> str:
        return api_url[self.run_mode]

    def _send_server_request(
        self,
        uri: str,
        method: str,
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        """Sends a request to the server and returns the response."""
        url = f"{self.url}/{uri}?save_questions=true"

        if method.upper() in ["GET", "DELETE"]:
            response = requests.request(
                method, url, params=params, headers=self.headers
            )
        else:
            response = requests.request(method, url, json=payload, headers=self.headers)

        return response

    def _resolve_server_response(self, response: requests.Response) -> None:
        """Checks the response from the server and raises appropriate errors."""
        if response.status_code >= 400:
            raise Exception(response.json().get("detail"))

    # QUESTIONS METHODS
    def create_question(self, question: Type[Question], public: bool = False) -> dict:
        """
        Creates a Question object.
        - `question`: the EDSL Question to be sent.
        - `public`: whether the question should be public (defaults to False)
        """
        response = self._send_server_request(
            uri="api/v0/questions",
            method="POST",
            payload={"json_string": json.dumps(question.to_dict()), "public": public},
        )
        self._resolve_server_response(response)
        return response.json()

    def get_question(self, id: int) -> Type[Question]:
        """Retrieves a Question object by id."""
        response = self._send_server_request(uri=f"api/v0/questions/{id}", method="GET")
        self._resolve_server_response(response)
        return Question.from_dict(json.loads(response.json().get("json_string")))

    @property
    def questions(self) -> list[dict[str, Union[int, Question]]]:
        """Retrieves all Questions."""
        response = self._send_server_request(uri="api/v0/questions", method="GET")
        self._resolve_server_response(response)
        questions = [
            {
                "id": q.get("id"),
                "question": Question.from_dict(json.loads(q.get("json_string"))),
            }
            for q in response.json()
        ]
        return questions

    def delete_question(self, id: int) -> dict:
        """Deletes a question from the coop."""
        response = self._send_server_request(
            uri=f"api/v0/questions/{id}", method="DELETE"
        )
        self._resolve_server_response(response)
        return response.json()

    # Surveys METHODS
    def create_survey(self, survey: Type[Survey], public: bool = False) -> dict:
        """
        Creates a Question object.
        - `survey`: the EDSL Survey to be sent.
        - `public`: whether the survey should be public (defaults to False)
        """
        response = self._send_server_request(
            uri="api/v0/surveys",
            method="POST",
            payload={"json_string": json.dumps(survey.to_dict()), "public": public},
        )
        self._resolve_server_response(response)
        return response.json()

    def get_survey(self, id: int) -> Type[Survey]:
        """Retrieves a Survey object by id."""
        response = self._send_server_request(uri=f"api/v0/surveys/{id}", method="GET")
        self._resolve_server_response(response)
        return Survey.from_dict(json.loads(response.json().get("json_string")))

    @property
    def surveys(self) -> list[dict[str, Union[int, Survey]]]:
        """Retrieves all Surveys."""
        response = self._send_server_request(uri="api/v0/surveys", method="GET")
        self._resolve_server_response(response)
        surveys = [
            {
                "id": q.get("id"),
                "survey": Survey.from_dict(json.loads(q.get("json_string"))),
            }
            for q in response.json()
        ]
        return surveys

    def delete_survey(self, id: int) -> dict:
        """Deletes a Survey from the coop."""
        response = self._send_server_request(
            uri=f"api/v0/surveys/{id}", method="DELETE"
        )
        self._resolve_server_response(response)
        return response.json()

    # AGENT METHODS
    def create_agent(
        self, agent: Union[Agent, AgentList], public: bool = False
    ) -> dict:
        """
        Creates an Agent or AgentList object.
        - `agent`: the EDSL Agent or AgentList to be sent.
        - `public`: whether the agent should be public (defaults to False)
        """
        response = self._send_server_request(
            uri="api/v0/agents",
            method="POST",
            payload={"json_string": json.dumps(agent.to_dict()), "public": public},
        )
        self._resolve_server_response(response)
        return response.json()

    def get_agent(self, id: int) -> Union[Agent, AgentList]:
        """Retrieves an Agent or AgentList object by id."""
        response = self._send_server_request(uri=f"api/v0/agents/{id}", method="GET")
        self._resolve_server_response(response)
        agent_dict = json.loads(response.json().get("json_string"))
        if "agent_list" in agent_dict:
            return AgentList.from_dict(agent_dict)
        else:
            return Agent.from_dict(agent_dict)

    @property
    def agents(self) -> list[dict[str, Union[int, Agent, AgentList]]]:
        """Retrieves all Agents and AgentLists."""
        response = self._send_server_request(uri="api/v0/agents", method="GET")
        self._resolve_server_response(response)
        agents = []
        for q in response.json():
            agent_dict = json.loads(q.get("json_string"))
            if "agent_list" in agent_dict:
                agent = AgentList.from_dict(agent_dict)
            else:
                agent = Agent.from_dict(agent_dict)
            agents.append({"id": q.get("id"), "agent": agent})
        return agents

    def delete_agent(self, id: int) -> dict:
        """Deletes an Agent or AgentList from the coop."""
        response = self._send_server_request(uri=f"api/v0/agents/{id}", method="DELETE")
        self._resolve_server_response(response)
        return response.json()

    # RESULTS METHODS
    def create_results(self, results: Results, public: bool = False) -> dict:
        """
        Creates a Results object.
        - `results`: the EDSL Results to be sent.
        - `public`: whether the Results should be public (defaults to False)
        """
        response = self._send_server_request(
            uri="api/v0/results",
            method="POST",
            payload={"json_string": json.dumps(results.to_dict()), "public": public},
        )
        self._resolve_server_response(response)
        return response.json()

    def get_results(self, id: int) -> Results:
        """Retrieves a Results object by id."""
        response = self._send_server_request(uri=f"api/v0/results/{id}", method="GET")
        self._resolve_server_response(response)
        return Results.from_dict(json.loads(response.json().get("json_string")))

    @property
    def results(self) -> list[dict[str, Union[int, Results]]]:
        """Retrieves all Results."""
        response = self._send_server_request(uri="api/v0/results", method="GET")
        self._resolve_server_response(response)
        results = [
            {
                "id": r.get("id"),
                "survey": Results.from_dict(json.loads(r.get("json_string"))),
            }
            for r in response.json()
        ]
        return results

    def delete_results(self, id: int) -> dict:
        """Deletes a Results object from the coop."""
        response = self._send_server_request(
            uri=f"api/v0/results/{id}", method="DELETE"
        )
        self._resolve_server_response(response)
        return response.json()


if __name__ == "__main__":
    from edsl.coop import Coop

    API_KEY = "O2ZMFnMATqZqeRbLFio5oILc79-GTz6rfQuXRpPFOEg"
    RUN_MODE = "development"
    coop = Coop(api_key=API_KEY, run_mode=RUN_MODE)

    # basics
    coop
    coop.headers
    coop.url

    ##############
    # A. QUESTIONS
    ##############
    from edsl.questions import QuestionMultipleChoice
    from edsl.questions import QuestionCheckBox
    from edsl.questions import QuestionFreeText

    # check questions on server (should be an empty list)
    coop.questions
    for question in coop.questions:
        coop.delete_question(question.get("id"))

    # get a question that does not exist (should return None)
    coop.get_question(id=1)

    # now post a Question
    coop.create_question(QuestionMultipleChoice.example())
    coop.create_question(QuestionCheckBox.example(), public=False)
    coop.create_question(QuestionFreeText.example(), public=True)

    # check all questions
    coop.questions

    # or get question by id
    coop.get_question(id=1)

    # delete the question
    coop.delete_question(id=1)

    # check all questions
    coop.questions

    ##############
    # B. Surveys
    ##############
    from edsl.surveys import Survey

    # check surveys on server (should be an empty list)
    coop.surveys
    for survey in coop.surveys:
        coop.delete_survey(survey.get("id"))

    # get a survey that does not exist (should return None)
    coop.get_survey(id=1)

    # now post a Survey
    coop.create_survey(Survey.example())
    coop.create_survey(Survey.example(), public=False)
    coop.create_survey(Survey.example(), public=True)
    coop.create_survey(Survey(), public=True)
    s = Survey().example()
    for i in range(10):
        q = QuestionFreeText.example()
        q.question_name = f"question_{i}"
        s.add_question(q)
    coop.create_survey(s, public=True)

    # check all surveys
    coop.surveys

    # or get survey by id
    coop.get_survey(id=1)

    # delete the survey
    coop.delete_survey(id=1)

    # check all surveys
    coop.surveys

    ##############
    # C. Agents and AgentLists
    ##############
    from edsl.agents import Agent, AgentList

    # check agents on server (should be an empty list)
    coop.agents
    for agent in coop.agents:
        coop.delete_agent(agent.get("id"))

    # get an agent that does not exist (should return None)
    coop.get_agent(id=2)

    # now post an Agent
    coop.create_agent(Agent.example())
    coop.create_agent(Agent.example(), public=False)
    coop.create_agent(Agent.example(), public=True)
    coop.create_agent(
        Agent(traits={"hair_type": "curly", "skil_color": "white"}), public=True
    )
    coop.create_agent(AgentList.example())
    coop.create_agent(AgentList.example(), public=False)
    coop.create_agent(AgentList.example(), public=True)

    # check all agents
    coop.agents

    # or get agent by id
    coop.get_agent(id=1)

    # delete the agent
    coop.delete_agent(id=1)

    # check all agents
    coop.agents

    ##############
    # D. Results
    ##############
    from edsl.results import Results

    # check results on server (should be an empty list)
    coop.results
    for results in coop.results:
        coop.delete_results(results.get("id"))

    # get a result that does not exist (should return None)
    coop.get_results(id=2)

    # now post a Results
    coop.create_results(Results.example())
    coop.create_results(Results.example(), public=False)
    coop.create_results(Results.example(), public=True)

    # check all results
    coop.results

    # or get results by id
    coop.get_results(id=1)

    # delete the results
    coop.delete_results(id=1)

    # check all results
    coop.results

    data = [
        [
            "0",
            "Florida Proud Boy Sentenced to 10 Years in Capitol Attack",
            "Christopher Worrell had gone on the run after his conviction last August, and was captured six weeks later.",
            "A Proud Boy from Florida who went on the lam after being convicted of using pepper spray on police officers during the attack on the Capitol on Jan. 6, 2021, was sentenced on Thursday to 10 years in prison.",
            "2024-01-05T03:06:42+0000",
        ],
        [
            "1",
            "Trump Ballot Challenges Advance, Varying Widely in Strategy and Sophistication",
            "Donald J. Trump's eligibility for the presidential ballot has been challenged in more than 30 states, but only a handful of those cases have gained traction so far.",
            "John Anthony Castro, a 40-year-old Texan, long-shot Republican presidential candidate and the most prolific challenger of Donald J. Trump's eligibility to be president, has gone to court in at least 27 states trying to remove the former president from the ballot.",
            "2024-01-04T21:11:21+0000",
        ],
        [
            "2",
            "In Tense Election Year, Public Officials Face Climate of Intimidation",
            "Colorado and Maine, which blocked former President Donald J. Trump from the ballot, have grappled with the harassment of officials.",
            "The caller had tipped off the authorities in Maine on Friday night: He told them that he had broken into the home of Shenna Bellows, the state's top election official, a Democrat who one night earlier had disqualified former President Donald J. Trump from the primary ballot because of his actions during the Jan. 6 Capitol riot.",
            "2024-01-04T10:02:27+0000",
        ],
        [
            "3",
            "The Case for Disqualifying Trump Is Strong",
            "Worrying about “consequences” is not a legal argument.",
            "It's been just over two weeks since the Colorado Supreme Court ruled that Section 3 of the 14th Amendment disqualifies Donald Trump from holding the office of president of the United States, and I spent way too much of my holiday vacation reading the legal and political commentary around the decision, and as I did so, I found myself experiencing déjà vu. Since the rise of Trump, he and his movement have transgressed constitutional, legal and moral boundaries at will and then, when Americans attempt to impose consequences for those transgressions, Trump's defenders and critics alike caution that the consequences will be dangerous or destabilizing.",
            "2024-01-04T10:02:30+0000",
        ],
        [
            "4",
            "The Thin Blue Line That Divides America",
            "The stark symbol wielded in the Capitol riot was always more complicated than it seemed.",
            "Among the banners that Donald Trump's supporters carried as they stormed the Capitol three years ago — 2016's Make America Great Again flags and 2020's Keep America Great flags, Confederate battle flags, Gadsden flags, Pine Tree flags, the Stars and Stripes — appeared a now-familiar variant of the American flag: white stars on a black field, with alternating black and white stripes, except for the stripe immediately beneath the union, which is blue.",
            "2024-01-04T10:00:51+0000",
        ],
        [
            "5",
            "The Jan. 6 Riot Inquiry So Far: Three Years, Hundreds of Prison Sentences",
            "More than 1,200 people have now been arrested in connection with the attack on the Capitol, and more than 450 sentenced to periods of incarceration. The investigation is far from over.",
            "More than 1,200 people have now been arrested in connection with the attack on the Capitol, and more than 450 sentenced to periods of incarceration. The investigation is far from over.",
            "2024-01-04T01:24:30+0000",
        ],
        [
            "6",
            "Trump Asks Supreme Court to Keep Him on Colorado Ballot",
            "The petition came in response to a Colorado Supreme Court ruling that the former president had engaged in insurrection and was ineligible to hold office under the 14th Amendment.",
            "Former President Donald J. Trump asked the U.S. Supreme Court on Wednesday to keep him on the primary ballot in Colorado, appealing an explosive ruling from the state Supreme Court declaring him ineligible based on his efforts to overturn the 2020 election that culminated in the Jan. 6, 2021, attack on the Capitol.",
            "2024-01-03T22:11:59+0000",
        ],
        [
            "7",
            "Former Guard Official Says Army Retaliated for His Account of Jan. 6 Delay",
            "Col. Earl Matthews, the top lawyer for the D.C. National Guard during the assault on the Capitol, said in a whistle-blower complaint that he was punished for contradicting the testimony of two top generals.",
            "A former top lawyer for the D.C. National Guard has accused Army officials of retaliating against him for asserting to Congress that two top Army officers lied about why deployment of the Guard was delayed during the Jan. 6, 2021, attack on the Capitol, according to a complaint filed with the Defense Department and obtained by The New York Times.",
            "2024-01-03T20:52:09+0000",
        ],
        [
            "8",
            "Biden Plans 2 Campaign Speeches to Underscore Contrasts With Trump",
            "The president will speak at Valley Forge on the anniversary of the Jan. 6 Capitol riot, and later at a South Carolina church where a white supremacist killed nine people.",
            "President Biden is intensifying his campaign efforts as he looks toward November, planning a series of speeches that aides said on Wednesday would cast the stakes of the coming election as the endurance of American democracy itself.",
            "2024-01-03T10:02:22+0000",
        ],
        [
            "9",
            "Trump Makes Another Pitch to Appeals Court on Immunity in Election Case",
            "The filing was the last step before an appeals court in Washington will hold a hearing on the crucial issue next week.",
            "Lawyers for former President Donald J. Trump on Tuesday made their final written request to a federal appeals court to grant Mr. Trump immunity to charges of plotting to overturn the 2020 election, arguing the indictment should be tossed out because it arose from actions he took while in the White House.",
            "2024-01-03T04:53:02+0000",
        ],
    ]

    import pandas as pd

    df = pd.DataFrame(
        data, columns=["index", "title", "sentence1", "sentence2", "timestamp"]
    )
    df = df[["title", "sentence1", "sentence2"]]
    df

    def add_content(df):
        from edsl.questions import QuestionFreeText
        from edsl import Scenario, Survey, Agent, Model

        # We create questions prompting the agent to provide the next sentence and to draft the next sentence
        q_direct = QuestionFreeText(
            question_name="direct",
            question_text="""Consider the recent news article \'{{ title }}\' that begins: {{ sentence1 }}.
            What is the next sentence in this article?""",
        )
        q_draft = QuestionFreeText(
            question_name="draft",
            question_text="""Consider a recent news article \'{{ title }}\' that begins: {{ sentence1 }}.
            Draft the next sentence in this article.""",
        )

        # We create scenarios of the questions with the article titles and first sentences
        scenarios = [
            Scenario({"title": row["title"], "sentence1": row["sentence1"]})
            for _, row in df.iterrows()
        ]

        # We create an agent that has total recall of recent articles and an agent that is capable of drafting an article
        agents = [
            Agent(
                name="total_recall",
                traits={"persona": "You have total recall of recent news articles."},
            ),
            Agent(
                name="great_writer",
                traits={"persona": "You are a world-class news journalist."},
            ),
        ]

        # We combine the questions into a survey
        survey = Survey(questions=[q_direct, q_draft])

        # We select an LLM
        models = [Model("gpt-4-1106-preview"), Model("gpt-3.5-turbo")]

        # We administer the survey with the data to both agents -- questions are administered asynchronously
        results = survey.by(scenarios).by(agents).by(models).run()

        return results

    results = add_content(df)

    results.data[1].answer
    coop.create_results(results)

    print(results.survey)
