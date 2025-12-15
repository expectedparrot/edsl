"""
Example usage of EXA API integration with EDSL ScenarioLists.

This file demonstrates how to use the EXA module to create ScenarioLists
from web search and enrichment data.
"""

import os
from edsl.scenarios.exa import from_exa, from_exa_webset


def example_sales_leaders():
    """Example: Search for sales leaders at fintech companies."""
    print("Example 1: Sales leaders at US fintech companies")

    scenarios = from_exa(
        query="Sales leaders at US fintech companies",
        criteria=[
            "currently holds a sales leadership position (e.g., head of sales, vp sales, sales director, or equivalent) at a company",
            "the company operates in the fintech industry",
            "the company is based in the united states",
        ],
        enrichments=[
            {"description": "Years of experience", "format": "number"},
            {"description": "University", "format": "text"},
        ],
        count=50,
    )

    print(f"Created ScenarioList with {len(scenarios)} scenarios")
    print(
        f"First scenario keys: {list(scenarios[0].keys()) if scenarios else 'No scenarios'}"
    )
    return scenarios


def example_tech_executives():
    """Example: Search for tech executives with different enrichments."""
    print("\nExample 2: Tech executives at startups")

    scenarios = from_exa(
        query="CTO and engineering leaders at AI startups",
        criteria=[
            "holds a technical leadership position (CTO, VP Engineering, Head of Engineering)",
            "works at a startup company focused on artificial intelligence or machine learning",
            "company was founded after 2020",
        ],
        enrichments=[
            {"description": "Previous companies worked at", "format": "list"},
            {"description": "GitHub or personal website URL", "format": "url"},
            {"description": "Technical expertise areas", "format": "list"},
        ],
        count=30,
    )

    print(f"Created ScenarioList with {len(scenarios)} scenarios")
    return scenarios


def example_from_webset():
    """Example: Load data from existing webset ID."""
    print("\nExample 3: Load from existing webset")

    # Using the example webset ID from the user's message
    webset_id = "01k6m4wn1aykv03jq3p4hxs2m9"

    try:
        scenarios = from_exa_webset(webset_id)
        print(
            f"Loaded ScenarioList with {len(scenarios)} scenarios from webset {webset_id}"
        )
        return scenarios
    except Exception as e:
        print(f"Failed to load webset {webset_id}: {e}")
        return None


def example_simple_search():
    """Example: Simple search without enrichments."""
    print("\nExample 4: Simple search without enrichments")

    scenarios = from_exa(query="Renewable energy companies in California", count=20)

    print(f"Created ScenarioList with {len(scenarios)} scenarios")
    return scenarios


def main():
    """Run all examples if EXA_API_KEY is available."""
    if not os.getenv("EXA_API_KEY"):
        print("EXA_API_KEY environment variable not found.")
        print("Set it to run these examples:")
        print("export EXA_API_KEY='your-api-key-here'")
        return

    try:
        # Run examples
        scenarios1 = example_sales_leaders()
        scenarios2 = example_tech_executives()
        scenarios3 = example_from_webset()
        scenarios4 = example_simple_search()

        print("\nAll examples completed successfully!")

        # Show some results if available
        if scenarios1:
            print(f"\nSample from sales leaders search:")
            print(scenarios1[0] if len(scenarios1) > 0 else "No results")

    except Exception as e:
        print(f"Error running examples: {e}")


if __name__ == "__main__":
    main()
