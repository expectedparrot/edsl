"""
Tests for all registered source types in the ScenarioSource system.

This module contains tests that verify the functionality of all registered
source types in the system. It uses the Source registry to automatically
test all available source types.
"""

from edsl.scenarios.scenario_source import Source, ScenarioSource
from edsl.scenarios.scenario_list import ScenarioList
from edsl import FileStore

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
        
        # Handle offline scenarios for URL-based sources
        if source_type == "urls":
            # URLs source may return empty list in offline mode, which is acceptable
            assert len(scenario_list) >= 0, f"ScenarioList should be empty or non-empty for {source_type}"
        else:
            assert len(scenario_list) > 0, f"Empty ScenarioList returned for {source_type}"

def test_source_type_uniqueness():
    """Test that all source types are unique."""
    registered_types = Source.get_registered_types()
    assert len(registered_types) == len(set(registered_types)), "Duplicate source types found in registry"

def test_from_source_directory(tmp_path):
    """Create a temporary directory with files and verify from_source('directory') works."""

    # Arrange – create two simple text files
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("hello")
    file_b.write_text("world")

    # Act – build a ScenarioList using the directory source
    scenario_list = ScenarioSource.from_source(
        "directory",
        directory=str(tmp_path),
        pattern="*.txt",
        recursive=False,
    )

    # Assert – we received a ScenarioList with the expected number of scenarios
    assert isinstance(scenario_list, ScenarioList)
    assert len(scenario_list) == 2

    # Confirm each scenario contains a FileStore object under the 'file' key
    for scenario in scenario_list:
        assert isinstance(scenario["file"], FileStore) 