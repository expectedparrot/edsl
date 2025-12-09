#!/usr/bin/env python3
"""
Demo script for AgentListInspectorWidget

This script provides an easy way to create and display the AgentListInspectorWidget
with sample data. Perfect for Jupyter notebooks or interactive Python sessions.
"""


def create_sample_agent_list():
    """Create a sample list of diverse agents for demonstration purposes."""
    from edsl.agents import Agent

    agents = []

    # Marketing Professional
    agents.append(
        Agent(
            name="Sarah Kim - Digital Marketing Manager",
            traits={
                "role": "digital_marketing_manager",
                "experience_years": 6,
                "specialties": ["social_media", "content_marketing", "seo"],
                "tools": ["google_analytics", "hootsuite", "semrush"],
                "industry": "e_commerce",
                "team_size": 8,
            },
            codebook={
                "role": "Current job position",
                "experience_years": "Years of marketing experience",
                "specialties": "Areas of marketing expertise",
                "tools": "Marketing tools and platforms used",
                "industry": "Industry sector focus",
                "team_size": "Number of team members managed",
            },
            trait_categories={
                "professional": ["role", "experience_years", "industry"],
                "expertise": ["specialties", "tools"],
                "management": ["team_size"],
            },
            instruction="I provide strategic marketing insights focused on digital channels and e-commerce growth.",
        )
    )

    # Data Scientist
    agents.append(
        Agent(
            name="Dr. Michael Chen - Senior Data Scientist",
            traits={
                "education": "phd_computer_science",
                "experience_years": 9,
                "languages": ["python", "r", "sql", "scala"],
                "specialties": ["machine_learning", "deep_learning", "nlp"],
                "industries": ["fintech", "healthcare"],
                "publications": 23,
            },
            codebook={
                "education": "Highest degree obtained",
                "experience_years": "Years in data science",
                "languages": "Programming languages proficient in",
                "specialties": "Technical specialization areas",
                "industries": "Industry domains worked in",
                "publications": "Research publications authored",
            },
            instruction="I provide technical data science solutions with emphasis on ML/AI applications in finance and healthcare.",
        )
    )

    # Product Manager
    agents.append(
        Agent(
            name="Lisa Wang - Senior Product Manager",
            traits={
                "role": "senior_product_manager",
                "experience_years": 7,
                "product_types": ["saas", "mobile_apps", "enterprise_software"],
                "methodologies": ["agile", "scrum", "design_thinking"],
                "metrics_focus": ["user_engagement", "retention", "revenue"],
                "company_stage": "series_b_startup",
            },
            codebook={
                "role": "Current product management role",
                "experience_years": "Years in product management",
                "product_types": "Types of products managed",
                "methodologies": "Product development methodologies used",
                "metrics_focus": "Key performance indicators tracked",
                "company_stage": "Current company growth stage",
            },
            traits_presentation_template="""Product Management Profile:
Role: {{role}} with {{experience_years}} years experience
Product Types: {{product_types|join(', ')}}
Methodologies: {{methodologies|join(', ')}}
KPI Focus: {{metrics_focus|join(', ')}}
Company: {{company_stage}}""",
            instruction="I offer strategic product management guidance for SaaS and mobile products in startup environments.",
        )
    )

    # Customer Success Manager
    agents.append(
        Agent(
            name="James Rodriguez - Customer Success Lead",
            traits={
                "role": "customer_success_manager",
                "experience_years": 5,
                "customer_segments": ["smb", "enterprise", "mid_market"],
                "tools": ["salesforce", "intercom", "gainsight"],
                "metrics": ["nps", "churn_rate", "expansion_revenue"],
                "team_size": 4,
            },
            codebook={
                "role": "Customer success role and level",
                "experience_years": "Years in customer success",
                "customer_segments": "Customer segments managed",
                "tools": "Customer success tools used",
                "metrics": "Key success metrics tracked",
                "team_size": "Size of team managed",
            },
            instruction="I focus on customer retention, expansion, and satisfaction across different customer segments.",
        )
    )

    # UX Designer
    agents.append(
        Agent(
            name="Emily Foster - Senior UX Designer",
            traits={
                "role": "senior_ux_designer",
                "experience_years": 8,
                "specialties": ["user_research", "interaction_design", "prototyping"],
                "tools": ["figma", "sketch", "principle", "miro"],
                "industries": ["fintech", "edtech", "healthtech"],
                "design_system_experience": True,
            },
            codebook={
                "role": "Current design role and seniority",
                "experience_years": "Years of UX design experience",
                "specialties": "UX design specialization areas",
                "tools": "Design tools and software used",
                "industries": "Industry verticals worked in",
                "design_system_experience": "Experience building design systems",
            },
            instruction="I provide user-centered design solutions with focus on fintech, edtech, and healthcare products.",
        )
    )

    # Simple agent for variety
    agents.append(
        Agent(
            name="Alex - General Assistant",
            traits={
                "personality": "helpful",
                "communication_style": "clear",
                "response_type": "concise",
            },
            instruction="I'm a helpful assistant focused on providing clear, concise responses.",
        )
    )

    return agents


def demo_list_widget():
    """Create and return a demo AgentListInspectorWidget."""
    from edsl.widgets import AgentListInspectorWidget

    agents = create_sample_agent_list()
    widget = AgentListInspectorWidget(agents)

    print("Demo AgentListInspectorWidget created!")
    summary = widget.export_summary()
    print(f"Agents: {summary['agent_count']}")
    print(f"Named agents: {summary['named_agents']}")
    print(f"Total traits: {summary['total_traits']}")
    print(f"Avg traits per agent: {summary['avg_traits_per_agent']:.1f}")
    print(f"Agents with categories: {summary['agents_with_categories']}")

    print("\nAgent list preview:")
    for i, agent in enumerate(agents):
        name = agent.name or f"Agent {i+1}"
        trait_count = len(agent.traits)
        print(f"  {i+1}. {name} ({trait_count} traits)")

    print("\nTo display in Jupyter: widget")
    print("Features:")
    print("- Click any agent card to inspect details")
    print("- Search across all agents")
    print("- Sort by name, trait count, or original order")
    print("- Responsive grid layout")

    return widget


def quick_list_demo():
    """Quick demo with a few simple agents for testing."""
    from edsl.agents import Agent
    from edsl.widgets import AgentListInspectorWidget

    agents = [
        Agent(
            name="Researcher",
            traits={"field": "AI", "experience": 5, "location": "Boston"},
            codebook={
                "field": "Research field",
                "experience": "Years of experience",
                "location": "Work location",
            },
        ),
        Agent(
            name="Designer",
            traits={"specialty": "UX", "tools": ["Figma", "Sketch"], "years": 3},
            codebook={
                "specialty": "Design specialty",
                "tools": "Design tools used",
                "years": "Years of experience",
            },
        ),
        Agent(
            name="Developer",
            traits={
                "languages": ["Python", "JavaScript"],
                "role": "Full-stack",
                "remote": True,
            },
            codebook={
                "languages": "Programming languages",
                "role": "Developer role",
                "remote": "Works remotely",
            },
        ),
    ]

    return AgentListInspectorWidget(agents)


if __name__ == "__main__":
    # For running directly in Python
    widget = demo_list_widget()
    print(f"\nWidget created: {widget}")
    print("In Jupyter, use: widget")
else:
    # For importing in notebooks
    print("AgentListInspectorWidget demo functions available:")
    print("- demo_list_widget(): Full-featured demo with 6 diverse agents")
    print("- quick_list_demo(): Simple test with 3 basic agents")
    print("- create_sample_agent_list(): Get the sample agents list")
