import textwrap
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Type, Union
from edsl.questions.Question import Question
from edsl.questions.schemas import QuestionData, AnswerData
from edsl.questions.settings import Settings


class QuestionExtractDataLists(Question):
    """Extracts a specified data type from a list of texts, storing information
    extracted from each text as a new list, and then returning a list of those
    lists (which may be different lengths depending on the content of each text).
    Each list starts with the number of the text (starting from 0) and then the
    extracted information."""

    question_type = "extract_data_lists"

    @property
    def instructions(self):
        return textwrap.dedent(
            """\
        You are being asked to extract certain information from a set of texts.
        {{question_text}}:
        {% for d in data %}
        {{ loop.index0 }}: {{d}}
        {% endfor %} 
        From each text, extract the following information as a new comma-separated list
        {{extract_data}} 
        Return all of the lists of extracted information in a valid JSON formatted exactly like this: 
        {"answer": [<put your list of lists here separated by commas>], "comment": "<put explanation here>"}         
        """
        )

    def __repr__(self):
        return f"""{self.__class__.__name__}(question_text = "{self.question_text}", extract_data = "{self.extract_data}", question_name = "{self.question_name}")"""

    @classmethod
    def construct_question_data_model(cls) -> Type[BaseModel]:
        class LocalQuestionData(QuestionData):
            """Pydantic data model for QuestionExtractData"""

            question_text: Optional[str] = Field(
                ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
            )
            extract_data: str = Field(
                ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
            )
            data: list[str] = Field(
                ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
            )
            allow_nonresponse: bool = None

        return LocalQuestionData

    def translate_answer_code_to_answer(self, answer, scenario=None):
        """There is no answer code."""
        return answer

    def construct_answer_data_model(self) -> Type[BaseModel]:
        class LocalAnswerDataModel(AnswerData):
            answer: list[list[Union[str, int]]] = Field(
                ..., min_length=0, max_length=Settings.MAX_ANSWER_LENGTH
            )

            @field_validator("answer")
            def check_answer(cls, value):
                if (
                    hasattr(self, "allow_nonresponse")
                    and self.allow_nonresponse == False
                    and (value == "" or value is None)
                ):
                    raise ValueError("You must provide a response.")
                return value

        return LocalAnswerDataModel

    def simulate_answer(self):
        "Simulates a valid answer for debugging purposes (what the validator expects)"
        raise NotImplementedError

    def form_elements(self):
        raise NotImplementedError

    # def __init__(self, question_text, extract_data, question_name=None):
    #     self.question_text = question_text
    #     self.extract_data = extract_data
    #     self.question_name = question_name

    #     d = {'question_text': question_text,
    #          'exptract_data': extract_data,
    #          'question_name': question_name}

    #     super().__init__(**d)


if __name__ == "__main__":
    from edsl import Agent, Scenario, print_dict_with_rich

    recipes = [
        """Classic Chocolate Chip Cookies
                Ingredients:

                1/2 cup (1 stick) unsalted butter, softened
                3/4 cup brown sugar, packed
                1/4 cup granulated sugar
                1 large egg
                2 teaspoons vanilla extract
                1.5 cups all-purpose flour
                1/2 teaspoon baking soda
                1/2 teaspoon salt
                1 cup chocolate chips
                1/2 cup chopped nuts (optional)
                Instructions:

                Preheat your oven to 350°F (175°C).
                In a large bowl, cream together the butter, brown sugar, and granulated sugar until light and fluffy.
                Beat in the egg and vanilla extract.
                In another bowl, whisk together the flour, baking soda, and salt. Gradually add this to the wet ingredients, stirring to incorporate.
                Fold in the chocolate chips and nuts, if using.
                Drop rounded tablespoons of dough onto a parchment-lined baking sheet, spacing them about 2 inches apart.
                Bake for 10-12 minutes or until golden around the edges but still soft in the center.
                Allow the cookies to cool on the baking sheet for a few minutes before transferring them to a wire rack to cool completely.""",
        """Easy Fruit Salad
                Ingredients:

                2 cups fresh pineapple chunks
                1 cup fresh strawberries, halved
                1 cup grapes, halved
                2 bananas, sliced
                1 apple, chopped
                1 cup yogurt or whipped cream for serving (optional)
                Instructions:

                In a large bowl, combine the pineapple, strawberries, grapes, bananas, and apple.
                Toss everything together until well mixed.
                Serve the fruit salad chilled, optionally topped with a dollop of yogurt or whipped cream.""",
        """Simple Rice Pudding
                Ingredients:

                1/2 cup uncooked white rice
                2 cups milk
                1/3 cup granulated sugar
                1/4 teaspoon salt
                1 egg, beaten
                2/3 cup raisins
                1 teaspoon vanilla extract
                1/2 teaspoon ground cinnamon (for serving)
                Instructions:

                In a medium saucepan, bring 1.5 cups of water to a boil. Stir in the rice and reduce the heat to low. Cover and simmer for 18-20 minutes, or until the rice is tender.
                Add the milk, sugar, and salt to the rice. Cook over medium heat until thick and creamy, 15 to 20 minutes, stirring frequently.
                Stir in the beaten egg and raisins. Cook for 2 more minutes, stirring constantly.
                Remove from heat and stir in the vanilla extract.
                Serve warm, sprinkled with a little ground cinnamon on top.""",
    ]

    q = QuestionExtractDataLists(
        question_text="The texts are recipes",
        extract_data="ingredients",
        data=recipes,
        question_name="ingredients",
    )
    scenarios = [Scenario({"recipe": recipe}) for recipe in recipes]
    print(q.get_prompt())
    results = q.by(*scenarios).run()
    print(results)

    # print(q.validate_answer(answer))
    # print(q.get_prompt())
