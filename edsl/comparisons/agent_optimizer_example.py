#!/usr/bin/env python3
"""
Simple example of using the AgentOptimizer framework for systematic agent improvement.

This example shows how to:
1. Set up a survey and gold standard
2. Create initial agents
3. Run the complete optimization process
4. Access results and logs
"""

from edsl import Survey, QuestionYesNo, QuestionCheckBox
from comparisons import AgentOptimizer
from comparisons.candidate_agent import CandidateAgent, CandidateAgentList

def main():
    print("🚀 AgentOptimizer Framework Demo")
    print("=" * 50)
    
    # 1. Define the survey
    survey = Survey([
        QuestionYesNo(
            question_text="Are you a nervous person?", 
            question_name="nervous"
        ),
        QuestionCheckBox(
            question_text="What are your hobbies?",
            question_name="hobbies",
            question_options=["Basketball", "Baseball", "Cooking", "Reading", "Writing", "Other"]
        ),
        QuestionYesNo(
            question_text="Have you ever traveled to Europe?", 
            question_name="europe"
        )
    ])
    
    # 2. Define gold standard answers
    gold_standard = {
        "nervous": "Yes",
        "hobbies": ["Basketball", "Cooking"],
        "europe": "Yes"
    }
    
    # 3. Create diverse starting agents
    starting_personas = [
        "I am a calm and collected person who loves sports",
        "I'm an anxious basketball player who enjoys cooking",
        "I'm a confident traveler with diverse interests",
        "I'm a nervous person who stays close to home",
        "I love basketball and trying new recipes"
    ]
    
    starting_agents = CandidateAgentList(
        [CandidateAgent(persona=persona, name=f"agent_{i}") 
         for i, persona in enumerate(starting_personas)],
        info=[f"Persona {i+1}" for i in range(len(starting_personas))]
    )
    
    print(f"📋 Survey: {len(survey.questions)} questions")
    print(f"👥 Starting agents: {len(starting_agents.agents)}")
    print(f"🎯 Gold standard: {list(gold_standard.keys())}")
    
    # 4. Create and run the optimizer
    optimizer = AgentOptimizer(
        survey=survey,
        gold_standard=gold_standard,
        starting_agents=starting_agents
    )
    
    # 5. Run optimization (change method to "all" to optimize every agent)
    results = optimizer.optimize(
        optimization_method="pareto",  # or "all", "top_percent", etc.
        max_suggestions_per_question=2,
        verbose=True,
        ask_confirmation=True
    )
    
    # 6. Access results
    print("\n📊 RESULTS SUMMARY:")
    results.print_summary()
    
    # 7. Show optimization details
    if len(results) > 0:
        print(f"\n📝 OPTIMIZATION LOG ({len(results.optimization_log)} entries):")
        for i, log_entry in enumerate(results.optimization_log):
            print(f"\n{i+1}. Agent: {log_entry['agent_name']}")
            print(f"   Questions improved: {list(log_entry['suggestions_per_question'].keys())}")
            print(f"   Final persona: {log_entry['improved_persona'][:100]}...")
    
    # 8. Access structured data for further analysis
    print(f"\n🔍 AVAILABLE DATA:")
    print(f"• Initial results: results.initial_results")
    print(f"• Final results: results.final_results")  
    print(f"• Optimization log: results.optimization_log")
    print(f"• Performance comparisons: results.final_comparisons")
    
    # 9. NEW: Access optimized agents with new prompts
    print(f"\n🚀 ACCESSING OPTIMIZED AGENTS WITH NEW PROMPTS:")
    print("="*60)
    
    # Method 1: Direct access to optimized agents
    if results.optimized_agents and results.optimized_agents.agents:
        print(f"\n📋 Method 1: Direct access (optimized_agents.agents)")
        for i, agent in enumerate(results.optimized_agents.agents):
            print(f"  Agent {i+1}: {agent.name}")
            print(f"  New Persona: {agent.persona}")
            print()
    
    # Method 2: Convert to EDSL AgentList (recommended for further surveys)
    print(f"🔄 Method 2: Convert to EDSL AgentList (recommended)")
    edsl_agents = results.to_edsl_agent_list()
    print(f"  Converted to EDSL AgentList with {len(edsl_agents)} agents")
    print(f"  Usage: new_survey.by(edsl_agents).run()")
    
    # Method 3: Helper methods
    print(f"\n📋 Method 3: Helper methods")
    print(f"  Optimized names: {results.get_optimized_names()}")
    print(f"  Number of personas: {len(results.get_optimized_personas())}")
    
    # Example of using optimized agents for new surveys
    print(f"\n💡 EXAMPLE: Using optimized agents for a new survey")
    if len(edsl_agents) > 0:
        from edsl import Survey, QuestionYesNo
        
        # Create a new survey
        confidence_survey = Survey([
            QuestionYesNo("Are you confident in your abilities?", "confident")
        ])
        
        print(f"  Created new survey: {confidence_survey.questions[0].question_text}")
        print(f"  Ready to run: confidence_survey.by(edsl_agents).run()")
        print(f"  The optimized personas will be used automatically!")
    
    return results

if __name__ == "__main__":
    results = main()
    print("\n✅ Demo completed! Results available in 'results' variable.") 