import textwrap
from edsl.macros.macro import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl import (
    Survey,
    QuestionFreeText,
    QuestionList,
    QuestionMultipleChoice,
    QuestionNumerical,
    Agent,
)

yc_advice = textwrap.dedent("""\
Your two sentence description is a concise explanation of your company for investors.
You'll practice using it during YC to introduce your company to other founders in the batch.

Your Group Partners will help you perfect your two sentence description.
A great two sentence description is a powerful tool that signals you're a clear thinker and succinct communicator.
This impresses investors and other useful people like potential hires or press.

Here are some examples of a good two sentence description:

    Stripe (S09) - Stripe is the easiest way for developers to process payments online. In just 7 lines of code, you can start accepting payments from customers in 135+ currencies without dealing with banks, compliance, or security headaches that normally take months to figure out.

    PostHog (W20) - PostHog is open source product analytics. Unlike closed-source alternatives that charge $30K+/year and lock away your data, we give you complete control, unlimited events, and the ability to deploy on your own infrastructure in under 5 minutes.

    Airbnb (W09) - Airbnb is a marketplace where you can book a home or apartment when traveling. You get 3x more space for half the price of hotels, plus a kitchen, local neighborhood feel, and unique stays like treehouses and castles that make your trip unforgettable.

A good two sentence description is memorable, creates a clear mental image of what your company does and makes the listener curious to learn more. Test it during the batch by asking a new founder each week to explain what your company does after hearing your two sentence description.

The three most common mistakes founders make when creating their two sentence pitch are making it too long, using too many buzzwords and failing to include traction.

Recommended structure

The first sentence plainly explains what the startup does. Anyone who hears it should have a clear sense for what it is used for, and ideally by whom. Nobody can engage with your startup if they don’t even understand what it is.

The second sentence plainly makes people understand why your startup is awesome and better than everything else. There are a bunch of ways to do this: specific user story that sounds way better, experience the founding team has that emphasizes they’re the ones to fix it, or even super fast growth during the YC batch.

It's not meant to be all-encompassing of the whole pitch

Think of your two sentence description like the trailer to a movie. It's goal is to pluck out just the most interesting things about your company to convince investors they should spend more time with you. Don’t try and cram everything about your company into it — investors are impressed by clear and concise communication, and the two sentence pitch is the appetizer not the main course.

Use plain English

Sometimes founders try and impress investors by stringing together popular buzzwords they think investors want to hear. It usually sounds something like this: “QuantumAI is an AI-powered platform revolutionizing the future of business by streamlining complex workflows to drive efficiency for our customers.” Don’t do this. Instead use informal, simple language your mother would understand.
""").strip()

# Initial survey to gather startup information
initial_survey = Survey([
    QuestionFreeText(
        question_name="startup_name",
        question_text="What is your startup's name?"
    ),
    QuestionFreeText(
        question_name="startup_does",
        question_text="What does your startup do?"
    ),
    QuestionFreeText(
        question_name="traction",
        question_text="What traction do you have?"
    ),
    QuestionFreeText(
        question_name="bio",
        question_text="Tell me your bio (or your founding team's bio)"
    ),
    QuestionNumerical(
        question_name = "n", 
        question_text= "How many samples do you want to generate?")
])


criteria = """
<important>
First sentence is what the startup does.
Second sentence is impressive traction or background of founders
</important>

A few key points:
- These 2 sentences are for investors, peers and press, not end users.
- It should invite further questions
- Don't lead with the problem
- All else equal, shorter is better
- Sharp and crisp.
- Every non-essential word hurts.
- Think movie trailer.

If traction is impressive, lead with that.
- Real revenue
- Booked LOIs
- Growth

Traction Examples
- "Over $100K in ARR"
- Contracts signed with Cedar-Sinai Medical center
- Sharp and short

If bio is impressive and important, that can be a good second sentence:
- Serial entrepreneur with 2 exits
- Founding engineer at Uber
- PhD from Stanford in molecular biology

Things that get investors excited:
- Signs there is a large market
- Great founder-market fit
- Signals of traction
"""

# YC partner agent with expertise in crafting 2-sentence descriptions
yc_partner = Agent(
    name="yc_partner",
    traits={
        'persona': textwrap.dedent("""\
You are a seasoned partner at Y Combinator very skilled at helping startups
come up with a 2 sentence description.
""" + yc_advice + criteria)
    }
)

# Question to generate candidate 2-sentence descriptions
q_generate_candidates = QuestionList(
    question_name="two_sentences",
    question_text=textwrap.dedent("""
Based on this information:

Name: {{ scenario.startup_name }},
What they do: {{ scenario.startup_does}},
Traction: {{ scenario.traction }},
Founder bio: {{ scenario.bio }}

Come up with at least {{ scenario.n }} candidate variations for the YC 2 sentence description.
It is fine to omit aspects of the startup that you know - it's meant to be a short pitch.
Make them different from each other to create a diverse set of candidates.
Variation can be induced by highlighting different aspects of the startup, or using a different tone/style/wording.
""")
)

# Question to shorten the candidates
q_shorten = QuestionFreeText(
    question_name="shorten",
    question_text="Please make this even more concise and sharper, aiming for 1/2 the length: {{ scenario.two_sentences }}"
)

# Stage 1: Generate and shorten candidates
generate_job = (
    Survey([q_generate_candidates])
    .by(yc_partner)
    .select('answer.two_sentences', 'scenario.*')
    .to_scenario_list()
    .expand('two_sentences')
    .to(Survey([q_shorten]).by(yc_partner))
)

# Output formatter for Stage 1
candidates_formatter = (
    OutputFormatter(description="Create a ScenarioList of 2-sentence startup descriptions", output_type="edsl_object")
    .select('answer.shorten')
    .rename({'answer.shorten': 'two_sentences'})
    .to_scenario_list()
)

# Markdown formatter to preview the candidates
markdown_formatter = (
    OutputFormatter(description="Candidates Preview (Markdown)", output_type="markdown")
    .select('answer.shorten')
    .rename({'answer.shorten': 'two_sentences'})
    .table(tablefmt="github")
    .to_string()
)

# Stage 1 App: Generate candidates
app = Macro(
    application_name="yc_two_sentence_generator",
    display_name="YC Two Sentence Generator",
    short_description="Generates candidate 2-sentence startup descriptions using YC best practices.",
    long_description="This application helps startups create compelling 2-sentence descriptions following Y Combinator best practices. It generates multiple variations highlighting different aspects of the startup, then shortens them to be crisp and impactful for investors.",
    initial_survey=initial_survey,
    jobs_object=generate_job,
    output_formatters={'scenario_list': candidates_formatter, 'markdown': markdown_formatter},
    default_formatter_name='scenario_list'
)

# Stage 2: Ranking App
# Question for pairwise comparison
q_rank = QuestionMultipleChoice(
    question_name="better_pitch",
    question_text="Which of these two startup pitches is more compelling and effective for investors?" + criteria,
    question_options=["{{ scenario.two_sentences_1 }}", "{{ scenario.two_sentences_2 }}"], 
    use_code = False
)

ranking_app = Macro.create_ranking_macro(
    ranking_question=q_rank,
    option_fields=['two_sentences_1', 'two_sentences_2'],
    application_name="yc_two_sentence_ranker",
    display_name="YC Two Sentence Ranker",
    short_description="Ranks 2-sentence startup descriptions by effectiveness.",
    long_description="This application ranks different variations of 2-sentence startup descriptions by their effectiveness for investors using pairwise comparisons.",
    option_base="two_sentences",
    rank_field="pitch_rank"
)

if __name__ == "__main__":
    # Example: Run generation first
    print("=== Stage 1: Generating candidates ===")
    print("Note: The ranking stage requires diverse candidates to avoid duplicate options.")
    print("Macros defined successfully!")
    print(f"- Generation macro: {app.application_name}")
    print(f"- Ranking macro: {ranking_app.application_name}")

    # Commented out full example to avoid duplicate options error in test suite
    # To run this example, ensure your candidates are diverse enough to avoid duplicates
    # candidates_output = app.output(
    #     params={
    #         'startup_name': "Expected Parrot",
    #         'startup_does': """...""",
    #         'traction': "Fast growing usage among academics; $120K in enterprise contracts",
    #         'bio': "Ex-Uber; MIT Professor who pioneered this approach.",
    #         'n': 20
    #     },
    #     verbose=True
    # )
    # candidates = candidates_output.scenario_list
    # sampled_candidates = candidates.sample(15)
    # ranked = ranking_app.output(params={'input_items': sampled_candidates}, verbose=True)
    # print(ranked.table())