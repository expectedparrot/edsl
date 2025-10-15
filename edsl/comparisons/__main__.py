#!/usr/bin/env python3

"""Demonstration of EDSL Comparisons module functionality.

This script showcases the core features of the comparisons module:
- Basic answer comparison using different metrics
- Results comparison with visualization
- Factory pattern for managing comparison functions
- Weighted scoring capabilities

Run with: python -m edsl.comparisons
"""

from __future__ import annotations

def main():
    """Demonstrate the main functionality of the comparisons module."""
    
    print("🔍 EDSL Comparisons Module Demo")
    print("=" * 50)
    
    # Demo 1: Basic comparison metrics
    print("\n1. Basic Comparison Metrics")
    print("-" * 30)
    
    from .metrics import ExactMatch, CosineSimilarity, Overlap, SquaredDistance
    
    # Sample answers to compare
    answers_a = ["I love programming", "Python is great", "Machine learning rocks"]
    answers_b = ["I enjoy coding", "Python is awesome", "ML is fantastic"]
    
    print(f"Answers A: {answers_a}")
    print(f"Answers B: {answers_b}")
    print()
    
    # Demonstrate different metrics
    metrics = [
        ExactMatch(),
        CosineSimilarity("all-MiniLM-L6-v2"),
        Overlap(),
        SquaredDistance()
    ]
    
    for metric in metrics:
        try:
            scores = metric.execute(answers_a, answers_b)
            print(f"{metric.short_name:25}: {scores}")
        except Exception as e:
            print(f"{metric.short_name:25}: Error - {e}")
    
    # Demo 2: Comparison Factory
    print("\n\n2. Comparison Factory")
    print("-" * 30)
    
    from .factory import ComparisonFactory
    
    # Create factory with defaults
    factory = ComparisonFactory.with_defaults()
    print(f"Available metrics: {[str(fn) for fn in factory.comparison_fns]}")
    
    try:
        results = factory.compare_answers(answers_a, answers_b)
        print("\nFactory results:")
        for metric_name, values in results.items():
            print(f"  {metric_name}: {values}")
    except Exception as e:
        print(f"Factory execution error: {e}")
        
    # Demo method chaining
    try:
        custom_factory = (ComparisonFactory()
                         .add_comparison(ExactMatch())
                         .add_comparison(Overlap()))
        print(f"\nCustom factory with method chaining: {[str(fn) for fn in custom_factory.comparison_fns]}")
        results = custom_factory.compare_answers(answers_a, answers_b)
        print("Custom factory results:")
        for metric_name, values in results.items():
            print(f"  {metric_name}: {values}")
    except Exception as e:
        print(f"Custom factory error: {e}")
    
    # Demo 3: Results Comparison (if EDSL is available)
    print("\n\n3. Results Comparison")
    print("-" * 30)
    
    try:
        from .result_pair_comparison import ResultPairComparison
        
        # Try to create an example comparison
        rc = ResultPairComparison.example()
        print("✅ Successfully created ResultPairComparison example")
        
        # Show basic comparison
        comparison = rc.compare()
        print(f"Number of questions compared: {len(comparison)}")
        print(f"Questions: {list(comparison.keys())}")
        
        # Display comparison table
        print("\nComparison Table:")
        try:
            rc.print_table()
        except Exception as e:
            print(f"Table display error: {e}")
        
        # Demo weighted scoring
        from .result_pair_comparison import (
            example_metric_weighting_dict,
            example_question_weighting_dict
        )
        
        try:
            metric_weights = example_metric_weighting_dict(rc.comparison_factory)
            question_weights = example_question_weighting_dict(rc)
            
            score = rc.weighted_score(metric_weights, question_weights)
            print(f"\nWeighted score: {score:.4f}")
            
        except Exception as e:
            print(f"Weighted scoring error: {e}")
        
    except ImportError as e:
        print(f"❌ Could not import EDSL Results: {e}")
        print("   Install EDSL to see full Results comparison features")
    except Exception as e:
        print(f"❌ Results comparison error: {e}")
    
    # Demo 4: Answer Comparison objects
    print("\n\n4. Answer Comparison Objects")
    print("-" * 30)
    
    from .answer_comparison import AnswerComparison
    
    # Create a sample AnswerComparison
    ac = AnswerComparison(
        answer_a="I love programming",
        answer_b="I enjoy coding",
        question_type="free_text",
        exact_match=False,
        cosine_similarity=0.85,
        overlap=0.0
    )
    
    print(f"Answer A: {ac.answer_a}")
    print(f"Answer B: {ac.answer_b}")
    print(f"Question type: {ac.question_type}")
    print(f"Exact match: {ac['exact_match']}")
    print(f"Cosine similarity: {ac['cosine_similarity']}")
    print(f"Overlap: {ac['overlap']}")
    
    # Demo 5: Agent Optimization Framework
    print("\n\n5. Agent Optimization Framework")
    print("-" * 30)
    
    # Import required modules
    from .agent_optimizer import AgentOptimizer
    from .candidate_agent import CandidateAgent, CandidateAgentList
    from edsl import Survey, QuestionFreeText, QuestionMultipleChoice, QuestionYesNo
    
    print("🤖 Creating sample agents for optimization...")
    
    # Create sample agents with different personas
    sample_agents = [
        CandidateAgent(
            name="helpful_assistant",
            persona="I am a helpful and friendly assistant who always tries to be polite and supportive."
        ),
        CandidateAgent(
            name="analytical_thinker", 
            persona="I approach problems analytically and focus on logical reasoning and evidence."
        ),
        CandidateAgent(
            name="creative_explorer",
            persona="I think creatively and like to explore unconventional solutions and perspectives."
        )
    ]
    
    agent_list = CandidateAgentList(sample_agents, ["Helpful", "Analytical", "Creative"])
    
    print(f"✅ Created {len(sample_agents)} sample agents")
    print("Agent personas:")
    for i, agent in enumerate(sample_agents):
        print(f"  {i+1}. {agent.name}: {agent.persona[:50]}...")
    
    print("\n📋 Creating sample survey...")
    
    # Create a simple survey
    survey = Survey([
        QuestionYesNo(
            question_text="Are you confident in your abilities?",
            question_name="confidence"
        ),
        QuestionMultipleChoice(
            question_text="What is your preferred problem-solving approach?",
            question_options=["Analytical", "Creative", "Collaborative", "Systematic"],
            question_name="approach"
        ),
        QuestionFreeText(
            question_text="Describe your ideal work environment in one word.",
            question_name="environment"
        )
    ])
    
    # Define gold standard answers
    gold_standard = {
        "confidence": "Yes",
        "approach": "Analytical", 
        "environment": "collaborative"
    }
    
    print("✅ Created sample survey with 3 questions")
    print(f"Gold standard: {gold_standard}")
    
    print("\n🔧 Initializing AgentOptimizer...")
    
    # Create optimizer
    optimizer = AgentOptimizer(
        survey=survey,
        gold_standard=gold_standard,
        starting_agents=agent_list
    )
    
    print("✅ AgentOptimizer initialized successfully")
    
    # Demonstrate the optimization process (but don't run full optimization)
    print("\n📊 Running initial performance evaluation...")
    
    initial_results, initial_comparisons = optimizer.evaluate_initial_performance(verbose=False)
    print(f"✅ Evaluated {len(sample_agents)} agents against gold standard")
    print(f"Initial performance data collected for {len(initial_comparisons)} comparisons")
    
    print("\n🎯 Identifying optimization targets...")
    target_agents = optimizer.identify_optimization_targets(selection_strategy="all", verbose=False)
    print(f"✅ Selected {len(target_agents.agents)} agents for potential optimization")
    
    print("\nOptimization process ready! Key features:")
    print("  • Multiple selection methods (pareto, all, top_percent)")
    print("  • LLM-driven persona improvements")
    print("  • Comprehensive performance analytics")
    print("  • Statistical significance testing")
    print("  • Export capabilities for further analysis")
    
    # Show what a full optimization would do
    print(f"\n💡 To run full optimization, call:")
    print(f"    results = optimizer.optimize()")
    print(f"    results.print_summary()")
    print(f"    edsl_agents = results.to_edsl_agent_list()")
    
    print("\n✨ Demo completed successfully!")
    print("\nFor more advanced usage, see:")
    print("  - PersonaPipeline for agent optimization workflows")
    print("  - AgentOptimizer for systematic improvements") 
    print("  - Visualization functions for metric heatmaps")
    print("  - Performance analytics for detailed optimization insights")


if __name__ == "__main__":
    main()