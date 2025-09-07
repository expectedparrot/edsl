#!/usr/bin/env python3
"""
Test script for the Unified Results Inspector Widget

This script creates sample EDSL Results data and displays it using the new
unified inspector widget that combines overview, results table, individual
result inspection, and statistical analysis capabilities.
"""

import sys
sys.path.append('/Users/johnhorton/tools/ep/edsl')

from edsl.widgets.unified_results_inspector import UnifiedResultsInspectorWidget

def create_sample_results():
    """Create sample Results object for testing the unified inspector."""
    
    try:
        # Try to create realistic EDSL objects
        from edsl import QuestionMultipleChoice, QuestionLinearScale, QuestionFreeText
        from edsl import Agent, Scenario, Survey, Model
        from edsl.language_models import LanguageModel
        
        # Create sample questions
        questions = [
            QuestionMultipleChoice(
                question_name="satisfaction",
                question_text="How satisfied are you with our service?",
                question_options=["Very Dissatisfied", "Dissatisfied", "Neutral", "Satisfied", "Very Satisfied"]
            ),
            QuestionLinearScale(
                question_name="rating",
                question_text="Please rate our service from 1-10",
                question_options=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
            ),
            QuestionFreeText(
                question_name="comments",
                question_text="Any additional comments?"
            ),
            QuestionMultipleChoice(
                question_name="recommendation",
                question_text="Would you recommend us to others?",
                question_options=["Yes", "No", "Maybe"]
            )
        ]
        
        # Create survey
        survey = Survey(questions=questions)
        
        # Create sample agents with different traits
        agents = [
            Agent(traits={"age": 25, "gender": "Female", "location": "Urban"}),
            Agent(traits={"age": 34, "gender": "Male", "location": "Suburban"}),
            Agent(traits={"age": 45, "gender": "Female", "location": "Rural"}),
            Agent(traits={"age": 28, "gender": "Male", "location": "Urban"}),
            Agent(traits={"age": 52, "gender": "Female", "location": "Suburban"}),
        ]
        
        # Create sample scenarios
        scenarios = [
            Scenario({"product": "Premium", "support_level": "High"}),
            Scenario({"product": "Standard", "support_level": "Medium"}),
            Scenario({"product": "Basic", "support_level": "Low"}),
            Scenario({"product": "Premium", "support_level": "Medium"}),
            Scenario({"product": "Standard", "support_level": "High"}),
        ]
        
        print("✅ Created EDSL objects successfully")
        print(f"   - Survey with {len(questions)} questions")
        print(f"   - {len(agents)} agents with different traits")  
        print(f"   - {len(scenarios)} scenarios")
        
        # For testing, we'll create mock Results since running actual surveys requires API keys
        print("📝 Note: Creating mock results for testing (actual survey execution requires API keys)")
        
        return create_mock_results(survey, agents, scenarios)
        
    except ImportError as e:
        print(f"⚠️ EDSL import error: {e}")
        print("📝 Creating minimal mock data for testing")
        return create_minimal_mock_results()

def create_mock_results(survey, agents, scenarios):
    """Create mock Results object with realistic structure."""
    
    try:
        from edsl import Results
        
        # Mock survey results data
        mock_results_data = []
        
        # Sample responses for testing
        sample_responses = [
            {"satisfaction": "Very Satisfied", "rating": 9, "comments": "Excellent service!", "recommendation": "Yes"},
            {"satisfaction": "Satisfied", "rating": 7, "comments": "Good overall experience", "recommendation": "Yes"},
            {"satisfaction": "Neutral", "rating": 5, "comments": "Average service", "recommendation": "Maybe"},
            {"satisfaction": "Satisfied", "rating": 8, "comments": "Very helpful staff", "recommendation": "Yes"},
            {"satisfaction": "Very Satisfied", "rating": 10, "comments": "Outstanding quality!", "recommendation": "Yes"},
            {"satisfaction": "Dissatisfied", "rating": 3, "comments": "Could be better", "recommendation": "No"},
            {"satisfaction": "Satisfied", "rating": 7, "comments": "Meets expectations", "recommendation": "Yes"},
            {"satisfaction": "Very Satisfied", "rating": 9, "comments": "Great value for money", "recommendation": "Yes"},
        ]
        
        # Create mock result objects
        for i, (agent, scenario) in enumerate(zip(agents * 2, scenarios * 2)):  # Create more results
            response = sample_responses[i % len(sample_responses)]
            
            # Mock result structure
            result_data = {
                "agent": {"traits": agent.traits},
                "scenario": {**scenario.data, "scenario_index": i},
                "answer": response,
                "model": {
                    "model": "gpt-4",
                    "inference_service": "openai",
                    "parameters": {"temperature": 0.7, "max_tokens": 1000}
                },
                "question_to_attributes": {
                    q.question_name: {
                        "question_text": q.question_text,
                        "question_type": type(q).__name__
                    } for q in survey.questions
                },
                "comments_dict": {f"{q.question_name}_comment": "" for q in survey.questions},
                "prompt": {f"{q.question_name}_user_prompt": {"text": f"Answer: {q.question_text}"} for q in survey.questions},
                "generated_tokens": {f"{q.question_name}_generated_tokens": str(response.get(q.question_name, "")) for q in survey.questions},
                "raw_model_response": {
                    f"{q.question_name}_input_tokens": 50 + i * 5,
                    f"{q.question_name}_output_tokens": 25 + i * 2,
                    f"{q.question_name}_cost": 0.001 + i * 0.0001,
                    f"{q.question_name}_input_price_per_million_tokens": 10.0,
                    f"{q.question_name}_output_price_per_million_tokens": 30.0,
                } for q in survey.questions
            }
            
            # Flatten the raw_model_response
            flattened_response = {}
            for q in survey.questions:
                flattened_response.update({
                    f"{q.question_name}_input_tokens": 50 + i * 5,
                    f"{q.question_name}_output_tokens": 25 + i * 2,
                    f"{q.question_name}_cost": 0.001 + i * 0.0001,
                    f"{q.question_name}_input_price_per_million_tokens": 10.0,
                    f"{q.question_name}_output_price_per_million_tokens": 30.0,
                })
            result_data["raw_model_response"] = flattened_response
            
            # Add system prompts
            system_prompts = {f"{q.question_name}_system_prompt": {"text": "You are a helpful assistant."} for q in survey.questions}
            result_data["prompt"].update(system_prompts)
            
            mock_results_data.append(result_data)
        
        print(f"✅ Created {len(mock_results_data)} mock results")
        
        # Create Results object with mock data
        from edsl.results.Results import Results
        
        # Create the Results object structure that the widget expects
        results_dict = {
            "survey": {
                "questions": [
                    {
                        "question_name": q.question_name,
                        "question_text": q.question_text,
                        "question_type": type(q).__name__
                    } for q in survey.questions
                ]
            },
            "data": mock_results_data
        }
        
        # Mock Results object
        class MockResults:
            def __init__(self, data, results_dict):
                self.data = data
                self._dict = results_dict
                
            def _summary(self):
                return {
                    "observations": len(self.data),
                    "questions": len(self._dict["survey"]["questions"]),
                    "agents": len(set(str(r["agent"]) for r in self.data)),
                    "scenarios": len(set(str(r["scenario"]) for r in self.data))
                }
                
            def to_dict(self):
                return self._dict
                
            def __len__(self):
                return len(self.data)
                
            def __getitem__(self, index):
                if isinstance(index, slice):
                    sliced_data = self.data[index]
                    return MockResults(sliced_data, {**self._dict, "data": sliced_data})
                return self.data[index]
                
            def to_dataset(self):
                """Convert to dataset format for analysis"""
                from types import SimpleNamespace
                
                # Convert results to flat format for analysis
                flat_data = []
                for result in self.data:
                    flat_row = {}
                    # Add answers with prefixes
                    for key, value in result["answer"].items():
                        flat_row[f"answer.{key}"] = value
                    # Add agent traits
                    for key, value in result["agent"]["traits"].items():
                        flat_row[f"agent.{key}"] = value
                    # Add scenario data
                    for key, value in result["scenario"].items():
                        if key not in ["edsl_class_name", "edsl_version", "scenario_index"]:
                            flat_row[f"scenario.{key}"] = value
                    flat_data.append(flat_row)
                
                dataset = SimpleNamespace()
                dataset.data = flat_data
                dataset.relevant_columns = lambda: list(flat_data[0].keys()) if flat_data else []
                dataset.to_dicts = lambda remove_prefix=True: flat_data
                
                return dataset
        
        results = MockResults(mock_results_data, results_dict)
        
        print(f"📊 Mock Results summary:")
        summary = results._summary()
        for key, value in summary.items():
            print(f"   - {key}: {value}")
            
        return results
        
    except Exception as e:
        print(f"⚠️ Error creating mock results: {e}")
        return create_minimal_mock_results()

def create_minimal_mock_results():
    """Create minimal mock results for basic testing."""
    
    print("🔧 Creating minimal mock results for basic functionality testing")
    
    # Minimal structure that the widget can handle
    class MinimalMockResults:
        def __init__(self):
            self.mock_data = [
                {
                    "agent": {"traits": {"test": "value1"}},
                    "scenario": {"setting": "test1"},
                    "answer": {"q1": "answer1"},
                    "model": {"model": "test-model", "inference_service": "test", "parameters": {}},
                    "question_to_attributes": {"q1": {"question_text": "Test question", "question_type": "TestQuestion"}},
                    "comments_dict": {"q1_comment": ""},
                    "prompt": {"q1_user_prompt": {"text": ""}, "q1_system_prompt": {"text": ""}},
                    "generated_tokens": {"q1_generated_tokens": ""},
                    "raw_model_response": {"q1_cost": 0.001, "q1_input_tokens": 10, "q1_output_tokens": 5}
                }
            ]
            self._dict = {
                "survey": {"questions": [{"question_name": "q1", "question_text": "Test question", "question_type": "TestQuestion"}]},
                "data": self.mock_data
            }
        
        def _summary(self):
            return {"observations": 1, "questions": 1, "agents": 1, "scenarios": 1}
            
        def to_dict(self):
            return self._dict
            
        def __len__(self):
            return len(self.mock_data)
            
        def __getitem__(self, index):
            return self.mock_data[index] if isinstance(index, int) else MinimalMockResults()
            
        def to_dataset(self):
            from types import SimpleNamespace
            dataset = SimpleNamespace()
            dataset.data = [{"answer.q1": "answer1", "agent.test": "value1", "scenario.setting": "test1"}]
            dataset.relevant_columns = lambda: ["answer.q1", "agent.test", "scenario.setting"]
            dataset.to_dicts = lambda remove_prefix=True: dataset.data
            return dataset
    
    return MinimalMockResults()

def main():
    """Main function to test the unified results inspector widget."""
    
    print("🚀 Testing Unified Results Inspector Widget")
    print("=" * 50)
    
    # Create sample results
    print("\n📋 Step 1: Creating sample Results object...")
    results = create_sample_results()
    
    if results is None:
        print("❌ Failed to create sample results")
        return
    
    # Create the unified widget
    print("\n🎨 Step 2: Creating Unified Results Inspector Widget...")
    try:
        widget = UnifiedResultsInspectorWidget(obj=results)
        print("✅ Widget created successfully!")
        
        # Display basic info about the widget
        print(f"\n📊 Widget Information:")
        print(f"   - Widget type: {type(widget).__name__}")
        print(f"   - Short name: {widget.widget_short_name}")
        print(f"   - Associated class: {widget.associated_class}")
        print(f"   - Page size: {widget.page_size}")
        print(f"   - Current page: {widget.current_page}")
        
        # Check if data was processed
        if hasattr(widget, 'results_data') and widget.results_data:
            print(f"   - Results data: ✅ Loaded ({len(widget.results_data.get('data', []))} results)")
        else:
            print(f"   - Results data: ⚠️ Not loaded yet")
            
        if hasattr(widget, 'analysis_data') and widget.analysis_data:
            print(f"   - Analysis data: ✅ Ready ({len(widget.analysis_data.get('dataset', []))} records)")
        else:
            print(f"   - Analysis data: ⚠️ Not ready yet")
        
        print(f"\n🎯 Step 3: Widget is ready for display!")
        print(f"   - In Jupyter: Just run the cell with 'widget' to see the interface")
        print(f"   - Features available:")
        print(f"     📋 Overview: Summary statistics and survey info")  
        print(f"     📊 Results: Paginated table with drill-down to individual results")
        print(f"     📈 Analysis: Statistical analysis and visualization tools") 
        print(f"     ⚙️ Settings: Configuration options")
        
        return widget
        
    except Exception as e:
        print(f"❌ Error creating widget: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Run the test
    widget = main()
    
    if widget:
        print(f"\n✨ Success! Widget is ready.")
        print(f"💡 To display in Jupyter notebook:")
        print(f"   from test_unified_inspector import main")
        print(f"   widget = main()")
        print(f"   widget  # This will display the interactive widget")
    else:
        print(f"\n❌ Widget creation failed.")