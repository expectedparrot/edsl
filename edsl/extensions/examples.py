"""
Example EDSL Services

This module contains example services that demonstrate how to use the EDSL service framework.
"""

from edsl import QuestionFreeText, QuestionNumerical, Agent, AgentList
from .service_framework import edsl_service, input_param, output_schema


@edsl_service(
    name="Simple Survey Service",
    description="A simple service that runs surveys with AI agents",
    version="1.0.0",
    cost_credits=3,
)
@input_param("topic", str, required=True, description="Topic to survey about")
@input_param(
    "num_agents",
    int,
    default=3,
    min_value=1,
    max_value=10,
    description="Number of AI agents to survey",
)
@input_param(
    "sentiment_level",
    str,
    default="neutral",
    choices=["positive", "neutral", "negative"],
    description="Sentiment level for agents",
)
@output_schema(
    {
        "topic": "str",
        "responses": "list",
        "summary": "str",
        "agent_count": "int",
        "average_rating": "float",
    }
)
def simple_survey_service(topic, num_agents, sentiment_level, ep_api_token):
    """
    Example service that runs a simple survey about any topic

    Args:
        topic: The topic to survey about
        num_agents: Number of AI agents to create
        sentiment_level: Sentiment for the agents
        ep_api_token: Expected Parrot API key

    Returns:
        Dictionary with survey results
    """

    # Create survey questions
    questions = QuestionFreeText(
        question_name="opinion", question_text=f"What do you think about {topic}?"
    ).add_question(
        QuestionNumerical(
            question_name="rating",
            question_text=f"On a scale of 1-10, how much do you care about {topic}?",
            min_value=1,
            max_value=10,
        )
    )

    # Create AI agents with different personalities
    agent_traits = []
    for i in range(num_agents):
        traits = {
            "personality": f"{sentiment_level}_person_{i+1}",
            "age": 25 + (i * 10),
            "background": f"Person with {sentiment_level} outlook",
        }
        agent_traits.append(traits)

    agents = AgentList([Agent(traits=traits) for traits in agent_traits])

    # Run the survey using EDSL
    results = questions.by(agents).run(expected_parrot_api_key=ep_api_token)

    # Process results
    responses = []
    total_rating = 0

    for result in results:
        response = {
            "agent_id": result.get("agent", {}).get("personality", "unknown"),
            "opinion": result.get("opinion", ""),
            "rating": result.get("rating", 0),
        }
        responses.append(response)
        total_rating += response["rating"]

    avg_rating = total_rating / len(responses) if responses else 0

    return {
        "topic": topic,
        "responses": responses,
        "summary": f"Surveyed {len(responses)} agents about {topic}. Average rating: {avg_rating:.1f}/10",
        "agent_count": len(responses),
        "average_rating": avg_rating,
    }


@edsl_service(
    name="Customer Feedback Analyzer",
    description="Analyzes customer feedback using diverse AI personas",
    version="1.0.0",
    cost_credits=5,
)
@input_param(
    "product_name", str, required=True, description="Name of the product to analyze"
)
@input_param(
    "feedback_text",
    str,
    required=True,
    min_length=10,
    description="Customer feedback text to analyze",
)
@input_param(
    "analysis_depth",
    str,
    default="standard",
    choices=["basic", "standard", "detailed"],
    description="Depth of analysis to perform",
)
@output_schema(
    {
        "product_name": "str",
        "sentiment_score": "float",
        "key_themes": "list",
        "recommendations": "list",
        "confidence": "float",
    }
)
def customer_feedback_analyzer(
    product_name, feedback_text, analysis_depth, ep_api_token
):
    """
    Analyzes customer feedback using multiple AI personas

    Args:
        product_name: Name of the product
        feedback_text: Customer feedback to analyze
        analysis_depth: How detailed the analysis should be
        ep_api_token: Expected Parrot API key

    Returns:
        Analysis results with sentiment and recommendations
    """

    # Create analysis questions based on depth
    questions = QuestionFreeText(
        question_name="sentiment_analysis",
        question_text=f"Analyze this customer feedback about {product_name}: '{feedback_text}'. What is the overall sentiment?",
    ).add_question(
        QuestionNumerical(
            question_name="sentiment_score",
            question_text="Rate the sentiment from -5 (very negative) to +5 (very positive)",
            min_value=-5,
            max_value=5,
        )
    )

    if analysis_depth in ["standard", "detailed"]:
        questions = questions.add_question(
            QuestionFreeText(
                question_name="key_themes",
                question_text="What are the main themes or topics mentioned in this feedback?",
            )
        )

    if analysis_depth == "detailed":
        questions = questions.add_question(
            QuestionFreeText(
                question_name="recommendations",
                question_text="Based on this feedback, what specific recommendations would you make?",
            )
        )

    # Create diverse analyst personas
    analyst_traits = [
        {"role": "customer_service_expert", "experience": "10_years"},
        {"role": "product_manager", "focus": "user_experience"},
        {"role": "market_researcher", "specialty": "sentiment_analysis"},
    ]

    agents = AgentList([Agent(traits=traits) for traits in analyst_traits])

    # Run analysis
    results = questions.by(agents).run(expected_parrot_api_key=ep_api_token)

    # Aggregate results
    sentiment_scores = [result.get("sentiment_score", 0) for result in results]
    avg_sentiment = (
        sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
    )

    # Extract themes and recommendations
    themes = []
    recommendations = []

    for result in results:
        if "key_themes" in result:
            themes.append(result["key_themes"])
        if "recommendations" in result:
            recommendations.append(result["recommendations"])

    # Calculate confidence based on agreement
    sentiment_std = (
        sum((s - avg_sentiment) ** 2 for s in sentiment_scores) / len(sentiment_scores)
    ) ** 0.5
    confidence = max(0, 1 - (sentiment_std / 5))  # Normalize to 0-1

    return {
        "product_name": product_name,
        "sentiment_score": avg_sentiment,
        "key_themes": themes,
        "recommendations": recommendations,
        "confidence": confidence,
    }
