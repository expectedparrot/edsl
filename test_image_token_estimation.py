#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script for image token estimation in EDSL.

This script verifies the implementation of token estimation for different
model types (Claude, Gemini, GPT-4) with various image sizes.
"""

import os
import sys
from pprint import pprint

# Add the repo root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from edsl.interviews.request_token_estimator import (
    approximate_image_tokens_claude,
    approximate_image_tokens_google,
    estimate_tokens,
)

def test_claude_token_estimation():
    """Test image token estimation for Claude models."""
    print("\n=== Testing Claude Image Token Estimation ===")
    
    # Test different image sizes with Claude 3 Opus
    image_sizes = [
        (800, 600),    # Standard image
        (1920, 1080),  # HD image
        (3840, 2160),  # 4K image
        (300, 300),    # Small square
        (5000, 3000),  # Very large image
    ]
    
    print("Claude 3 Opus token estimates for different image sizes:")
    for width, height in image_sizes:
        tokens = approximate_image_tokens_claude(width, height, claude_model="claude-3-opus")
        pixels = width * height
        print(f"  {width}x{height} ({pixels:,} pixels): {tokens:,} tokens")
    
    # Test different Claude models with same image
    width, height = 1024, 768
    pixels = width * height
    
    print(f"\nToken estimates for different Claude models (image size: {width}x{height}, {pixels:,} pixels):")
    claude_models = [
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
        "claude",  # Generic
        "claude-3-unknown",  # Should fall back to generic
    ]
    
    for model in claude_models:
        tokens = approximate_image_tokens_claude(width, height, claude_model=model)
        print(f"  {model}: {tokens:,} tokens")

def test_gemini_token_estimation():
    """Test image token estimation for Gemini models."""
    print("\n=== Testing Gemini Image Token Estimation ===")
    
    # Test different image sizes with Gemini
    image_sizes = [
        (300, 300),    # Small image
        (400, 400),    # Just over the threshold
        (800, 600),    # Standard image
        (1920, 1080),  # HD image
        (3840, 2160),  # 4K image
    ]
    
    print("Gemini token estimates for different image sizes:")
    for width, height in image_sizes:
        tokens = approximate_image_tokens_google(width, height)
        pixels = width * height
        print(f"  {width}x{height} ({pixels:,} pixels): {tokens:,} tokens")

def test_unified_estimator():
    """Test the unified token estimator for different models."""
    print("\n=== Testing Unified Token Estimator ===")
    
    # Define combinations of models and image sizes
    test_cases = [
        ("claude-3-opus", 1024, 768),
        ("claude-3-sonnet", 1024, 768),
        ("claude", 1024, 768),
        ("gemini-pro-vision", 1024, 768),
        ("gpt-4o", 1024, 768),
        ("unknown-model", 1024, 768),
        
        # Different image sizes with the same model
        ("claude-3-opus", 300, 300),
        ("claude-3-opus", 1920, 1080),
        ("claude-3-opus", 3840, 2160),
    ]
    
    print("Unified token estimates for different models and image sizes:")
    for model, width, height in test_cases:
        tokens = estimate_tokens(model, width, height)
        pixels = width * height
        print(f"  {model} with {width}x{height} ({pixels:,} pixels): {tokens:,} tokens")

def main():
    """Run tests for all token estimation functions."""
    print("Testing Image Token Estimation in EDSL")
    print("=====================================")
    
    test_claude_token_estimation()
    test_gemini_token_estimation()
    test_unified_estimator()
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    main()