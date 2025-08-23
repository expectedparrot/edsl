#!/usr/bin/env python3
"""
Simple test script to verify n parameter functionality without pytest.
"""

import sys
import os

# Add the edsl package to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_basic_n_parameter():
    """Test basic n parameter functionality."""
    print("Testing basic n parameter functionality...")
    
    try:
        from edsl.inference_services.services.open_ai_service import OpenAIService
        
        # Create a model with n=5
        model_class = OpenAIService.create_model("gpt-3.5-turbo")
        model = model_class(skip_api_key_check=True, n=5)
        
        assert model.n == 5, f"Expected n=5, got {model.n}"
        print("✓ OpenAI n parameter test passed")
        
    except Exception as e:
        print(f"✗ OpenAI n parameter test failed: {e}")
        return False
    
    try:
        from edsl.inference_services.services.google_service import GoogleService
        
        # Create a model with candidateCount=3
        model_class = GoogleService.create_model("gemini-pro")
        model = model_class(skip_api_key_check=True, candidateCount=3)
        
        assert model.candidateCount == 3, f"Expected candidateCount=3, got {model.candidateCount}"
        print("✓ Google candidateCount parameter test passed")
        
    except Exception as e:
        print(f"✗ Google candidateCount parameter test failed: {e}")
        return False
        
    try:
        from edsl.inference_services.services.anthropic_service import AnthropicService
        
        # Create a model with n=2 (should use fallback)
        model_class = AnthropicService.create_model("claude-3-opus-20240229")
        model = model_class(skip_api_key_check=True, n=2)
        
        assert model.n == 2, f"Expected n=2, got {model.n}"
        print("✓ Anthropic n parameter fallback test passed")
        
    except Exception as e:
        print(f"✗ Anthropic n parameter fallback test failed: {e}")
        return False
    
    return True

def test_get_all_completions():
    """Test the get_all_completions method."""
    print("\nTesting get_all_completions functionality...")
    
    try:
        from edsl.language_models.language_model import LanguageModel
        
        # Test OpenAI format
        openai_response = {
            "choices": [
                {"index": 0, "message": {"content": "First completion"}},
                {"index": 1, "message": {"content": "Second completion"}},
            ]
        }
        
        completions = LanguageModel.get_all_completions(openai_response)
        assert len(completions) == 2, f"Expected 2 completions, got {len(completions)}"
        assert completions[0] == "First completion", f"Expected 'First completion', got {completions[0]}"
        assert completions[1] == "Second completion", f"Expected 'Second completion', got {completions[1]}"
        print("✓ OpenAI format get_all_completions test passed")
        
        # Test Google format
        google_response = {
            "candidates": [
                {"content": {"parts": [{"text": "First candidate"}]}},
                {"content": {"parts": [{"text": "Second candidate"}]}},
            ]
        }
        
        completions = LanguageModel.get_all_completions(google_response)
        assert len(completions) == 2, f"Expected 2 completions, got {len(completions)}"
        assert completions[0] == "First candidate", f"Expected 'First candidate', got {completions[0]}"
        assert completions[1] == "Second candidate", f"Expected 'Second candidate', got {completions[1]}"
        print("✓ Google format get_all_completions test passed")
        
    except Exception as e:
        print(f"✗ get_all_completions test failed: {e}")
        return False
    
    return True

def main():
    """Run all tests."""
    print("Running n parameter implementation tests...\n")
    
    success = True
    
    if not test_basic_n_parameter():
        success = False
    
    if not test_get_all_completions():
        success = False
    
    if success:
        print("\n🎉 All tests passed! n parameter implementation is working correctly.")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    exit(main())