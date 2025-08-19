#!/usr/bin/env python3
"""
Demo script for AgentInspectorWidget

This script provides an easy way to create and display the AgentInspectorWidget
with sample data. Perfect for Jupyter notebooks or interactive Python sessions.
"""


def create_sample_agent():
    """Create a sample agent for demonstration purposes."""
    from edsl.agents import Agent

    return Agent(
        name="Dr. Elena Rodriguez - Market Research Expert",
        traits={
            # Professional Background
            "role": "senior_market_analyst",
            "company": "global_insights_corp",
            "years_experience": 8,
            "education": "mba_marketing",
            # Expertise Areas
            "industries": ["technology", "healthcare", "finance"],
            "methodologies": ["quantitative_analysis", "focus_groups", "surveys"],
            "tools": ["spss", "tableau", "python", "excel"],
            # Geographic Focus
            "primary_markets": ["north_america", "europe"],
            "languages": ["english", "spanish", "portuguese"],
            # Personal Traits
            "communication_style": "data_driven_storytelling",
            "decision_making": "analytical_collaborative",
            "innovation_approach": "user_centered_design",
        },
        codebook={
            # Professional Background
            "role": "Current job title and level of seniority",
            "company": "Current employer organization",
            "years_experience": "Total years of professional market research experience",
            "education": "Highest relevant degree completed",
            # Expertise Areas
            "industries": "Industry sectors with deep expertise",
            "methodologies": "Research methodologies frequently employed",
            "tools": "Software tools and platforms regularly used",
            # Geographic Focus
            "primary_markets": "Geographic regions of primary focus",
            "languages": "Languages spoken fluently for international research",
            # Personal Traits
            "communication_style": "Preferred approach to presenting findings",
            "decision_making": "Style of making research and business decisions",
            "innovation_approach": "Philosophy toward developing new research approaches",
        },
        trait_categories={
            "professional": ["role", "company", "years_experience", "education"],
            "expertise": ["industries", "methodologies", "tools"],
            "geographic": ["primary_markets", "languages"],
            "personal": [
                "communication_style",
                "decision_making",
                "innovation_approach",
            ],
        },
        traits_presentation_template="""As a market research professional, here are my key attributes:

Professional Background:
- Role: {{role}} at {{company}}
- Experience: {{years_experience}} years in the field
- Education: {{education}}

Areas of Expertise:
- Industry Focus: {{industries|join(', ')}}
- Research Methods: {{methodologies|join(', ')}}
- Tools & Platforms: {{tools|join(', ')}}

Geographic & Cultural Scope:
- Primary Markets: {{primary_markets|join(', ')}}
- Languages: {{languages|join(', ')}}

Personal Working Style:
- Communication: {{communication_style}}
- Decision Making: {{decision_making}}  
- Innovation Philosophy: {{innovation_approach}}""",
        instruction="""I am Dr. Elena Rodriguez, a senior market research analyst with 8 years of experience across technology, healthcare, and finance industries.

My approach to answering questions:
• Ground insights in quantitative data and established research methodologies
• Consider cultural and regional differences in market behaviors
• Balance statistical significance with practical business implications
• Communicate findings through clear data storytelling
• Acknowledge limitations and confidence intervals in research conclusions

I excel at:
- Designing and executing comprehensive market research studies
- Identifying consumer behavior patterns and trends
- Creating actionable recommendations from complex datasets  
- Cross-cultural market analysis and segmentation
- Collaborative stakeholder engagement and consensus building

I always consider ethical research practices and data privacy regulations in my recommendations.""",
    )


def demo_widget():
    """Create and return a demo AgentInspectorWidget."""
    from edsl.widgets import AgentInspectorWidget

    agent = create_sample_agent()
    widget = AgentInspectorWidget(agent)

    print("Demo AgentInspectorWidget created!")
    print("Agent:", agent.name)
    print("Traits:", len(agent.traits))
    print("Codebook entries:", len(agent.codebook))
    print("Categories:", len(agent.trait_categories) if agent.trait_categories else 0)
    print("\nTo display in Jupyter: widget")

    return widget


def quick_demo():
    """Quick demo with minimal agent for testing."""
    from edsl.agents import Agent
    from edsl.widgets import AgentInspectorWidget

    agent = Agent(
        name="Quick Test Agent",
        traits={
            "age": 28,
            "profession": "data_scientist",
            "skills": ["python", "sql", "machine_learning"],
            "location": "san_francisco",
        },
        codebook={
            "age": "Age in years",
            "profession": "Current job role",
            "skills": "Technical skills and competencies",
            "location": "Current city of residence",
        },
    )

    return AgentInspectorWidget(agent)


if __name__ == "__main__":
    # For running directly in Python
    widget = demo_widget()
    print(f"\nWidget created: {widget}")
    print("In Jupyter, use: widget")
else:
    # For importing in notebooks
    print("AgentInspectorWidget demo functions available:")
    print("- demo_widget(): Full-featured demo agent")
    print("- quick_demo(): Simple test agent")
    print("- create_sample_agent(): Get the sample agent object")
