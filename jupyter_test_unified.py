"""
Simple Jupyter notebook test for Unified Results Inspector Widget

Copy and paste this code into a Jupyter notebook cell to test the widget.
"""

# Import the widget
import sys
sys.path.append('/Users/johnhorton/tools/ep/edsl')

from edsl.widgets.unified_results_inspector import UnifiedResultsInspectorWidget

def create_quick_test_results():
    """Create quick test results for immediate testing."""
    
    class QuickTestResults:
        def __init__(self):
            # Sample survey responses
            self.sample_data = [
                {
                    "agent": {"traits": {"age": 25, "gender": "Female", "location": "Urban"}},
                    "scenario": {"product": "Premium", "support_level": "High"},
                    "answer": {
                        "satisfaction": "Very Satisfied", 
                        "rating": 9, 
                        "comments": "Excellent service!",
                        "recommendation": "Yes"
                    },
                    "model": {"model": "gpt-4", "inference_service": "openai", "parameters": {"temperature": 0.7}},
                    "question_to_attributes": {
                        "satisfaction": {"question_text": "How satisfied are you?", "question_type": "MultipleChoice"},
                        "rating": {"question_text": "Rate 1-10", "question_type": "LinearScale"},
                        "comments": {"question_text": "Any comments?", "question_type": "FreeText"},
                        "recommendation": {"question_text": "Would you recommend us?", "question_type": "MultipleChoice"}
                    },
                    "comments_dict": {q + "_comment": "" for q in ["satisfaction", "rating", "comments", "recommendation"]},
                    "prompt": {
                        **{q + "_user_prompt": {"text": f"Please answer: {q}"} for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_system_prompt": {"text": "You are a helpful assistant."} for q in ["satisfaction", "rating", "comments", "recommendation"]}
                    },
                    "generated_tokens": {q + "_generated_tokens": "Generated response" for q in ["satisfaction", "rating", "comments", "recommendation"]},
                    "raw_model_response": {
                        **{q + "_input_tokens": 50 for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_output_tokens": 25 for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_cost": 0.001 for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_input_price_per_million_tokens": 10.0 for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_output_price_per_million_tokens": 30.0 for q in ["satisfaction", "rating", "comments", "recommendation"]}
                    }
                },
                {
                    "agent": {"traits": {"age": 34, "gender": "Male", "location": "Suburban"}},
                    "scenario": {"product": "Standard", "support_level": "Medium"},
                    "answer": {
                        "satisfaction": "Satisfied", 
                        "rating": 7, 
                        "comments": "Good service overall",
                        "recommendation": "Yes"
                    },
                    "model": {"model": "gpt-4", "inference_service": "openai", "parameters": {"temperature": 0.7}},
                    "question_to_attributes": {
                        "satisfaction": {"question_text": "How satisfied are you?", "question_type": "MultipleChoice"},
                        "rating": {"question_text": "Rate 1-10", "question_type": "LinearScale"},
                        "comments": {"question_text": "Any comments?", "question_type": "FreeText"},
                        "recommendation": {"question_text": "Would you recommend us?", "question_type": "MultipleChoice"}
                    },
                    "comments_dict": {q + "_comment": "" for q in ["satisfaction", "rating", "comments", "recommendation"]},
                    "prompt": {
                        **{q + "_user_prompt": {"text": f"Please answer: {q}"} for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_system_prompt": {"text": "You are a helpful assistant."} for q in ["satisfaction", "rating", "comments", "recommendation"]}
                    },
                    "generated_tokens": {q + "_generated_tokens": "Generated response" for q in ["satisfaction", "rating", "comments", "recommendation"]},
                    "raw_model_response": {
                        **{q + "_input_tokens": 45 for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_output_tokens": 20 for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_cost": 0.0008 for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_input_price_per_million_tokens": 10.0 for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_output_price_per_million_tokens": 30.0 for q in ["satisfaction", "rating", "comments", "recommendation"]}
                    }
                },
                {
                    "agent": {"traits": {"age": 45, "gender": "Female", "location": "Rural"}},
                    "scenario": {"product": "Basic", "support_level": "Low"},
                    "answer": {
                        "satisfaction": "Neutral", 
                        "rating": 5, 
                        "comments": "Average experience",
                        "recommendation": "Maybe"
                    },
                    "model": {"model": "gpt-4", "inference_service": "openai", "parameters": {"temperature": 0.7}},
                    "question_to_attributes": {
                        "satisfaction": {"question_text": "How satisfied are you?", "question_type": "MultipleChoice"},
                        "rating": {"question_text": "Rate 1-10", "question_type": "LinearScale"},
                        "comments": {"question_text": "Any comments?", "question_type": "FreeText"},
                        "recommendation": {"question_text": "Would you recommend us?", "question_type": "MultipleChoice"}
                    },
                    "comments_dict": {q + "_comment": "" for q in ["satisfaction", "rating", "comments", "recommendation"]},
                    "prompt": {
                        **{q + "_user_prompt": {"text": f"Please answer: {q}"} for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_system_prompt": {"text": "You are a helpful assistant."} for q in ["satisfaction", "rating", "comments", "recommendation"]}
                    },
                    "generated_tokens": {q + "_generated_tokens": "Generated response" for q in ["satisfaction", "rating", "comments", "recommendation"]},
                    "raw_model_response": {
                        **{q + "_input_tokens": 40 for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_output_tokens": 18 for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_cost": 0.0006 for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_input_price_per_million_tokens": 10.0 for q in ["satisfaction", "rating", "comments", "recommendation"]},
                        **{q + "_output_price_per_million_tokens": 30.0 for q in ["satisfaction", "rating", "comments", "recommendation"]}
                    }
                }
            ]
            
            self._dict = {
                "survey": {
                    "questions": [
                        {"question_name": "satisfaction", "question_text": "How satisfied are you with our service?", "question_type": "MultipleChoice"},
                        {"question_name": "rating", "question_text": "Please rate our service from 1-10", "question_type": "LinearScale"},
                        {"question_name": "comments", "question_text": "Any additional comments?", "question_type": "FreeText"},
                        {"question_name": "recommendation", "question_text": "Would you recommend us to others?", "question_type": "MultipleChoice"}
                    ]
                },
                "data": self.sample_data
            }
        
        def _summary(self):
            return {
                "observations": len(self.sample_data),
                "questions": 4,
                "agents": 3,
                "scenarios": 3
            }
            
        def to_dict(self):
            return self._dict
            
        def __len__(self):
            return len(self.sample_data)
            
        def __getitem__(self, index):
            if isinstance(index, slice):
                return QuickTestResults()  # Simplified for testing
            return self.sample_data[index]
            
        def to_dataset(self):
            """Convert to dataset format for analysis"""
            from types import SimpleNamespace
            
            # Convert to flat format
            flat_data = []
            for result in self.sample_data:
                flat_row = {}
                # Add answers
                for key, value in result["answer"].items():
                    flat_row[f"answer.{key}"] = value
                # Add agent traits
                for key, value in result["agent"]["traits"].items():
                    flat_row[f"agent.{key}"] = value
                # Add scenario data
                for key, value in result["scenario"].items():
                    flat_row[f"scenario.{key}"] = value
                flat_data.append(flat_row)
            
            dataset = SimpleNamespace()
            dataset.data = flat_data
            dataset.relevant_columns = lambda: list(flat_data[0].keys()) if flat_data else []
            dataset.to_dicts = lambda remove_prefix=True: flat_data
            
            return dataset
    
    return QuickTestResults()

# Create and display the widget
print("🚀 Creating Unified Results Inspector Widget...")

# Create sample data
results = create_quick_test_results()
print("✅ Sample results created")

# Create the widget
widget = UnifiedResultsInspectorWidget(obj=results)
print("✅ Widget created successfully!")

print("\n📊 Widget Features:")
print("   📋 Overview Tab: Survey summary and statistics")
print("   📊 Results Tab: Click any row to drill down to individual result details")  
print("   📈 Analysis Tab: Statistical analysis and visualization tools")
print("   ⚙️ Settings Tab: Configure display options")

print("\n💡 The widget is ready to display!")
print("   Run 'widget' in the next cell to see the interactive interface")

# Export the widget for easy access
widget