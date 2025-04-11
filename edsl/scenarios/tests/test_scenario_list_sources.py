"""
Tests for all registered source types in the ScenarioSource system.

This module contains tests that verify the functionality of all registered
source types in the system. It uses the Source registry to automatically
test all available source types.
"""

from edsl.scenarios.scenario_source import Source
from edsl.scenarios.scenario_list import ScenarioList

def test_all_source_types():
    """
    Test that all registered source types can create an example instance
    and convert it to a ScenarioList.
    """
    results = Source.test_all_sources()
    
    # Print detailed results for debugging
    for source_type, success in results.items():
        print(f"Source type {source_type}: {'✓' if success else '✗'}")
    
    # Assert that all source types succeeded
    failed_sources = [source_type for source_type, success in results.items() if not success]
    assert not failed_sources, f"The following source types failed: {failed_sources}"

def test_source_registry_not_empty():
    """Test that the source registry is not empty."""
    registered_types = Source.get_registered_types()
    assert len(registered_types) > 0, "No source types are registered"

def test_each_source_type():
    """
    Test each source type individually with more detailed assertions.
    """
    for source_type in Source.get_registered_types():
        source_class = Source.get_source_class(source_type)
        
        # Test example creation
        example = source_class.example()
        assert example is not None, f"Example creation failed for {source_type}"
        
        # Test to_scenario_list
        scenario_list = example.to_scenario_list()
        assert isinstance(scenario_list, ScenarioList), f"to_scenario_list did not return a ScenarioList for {source_type}"
        assert len(scenario_list) > 0, f"Empty ScenarioList returned for {source_type}"

def test_source_type_uniqueness():
    """Test that all source types are unique."""
    registered_types = Source.get_registered_types()
    assert len(registered_types) == len(set(registered_types)), "Duplicate source types found in registry" 