import pytest
from edsl.scenarios import Scenario, ScenarioList
from edsl.scenarios.scenario_selector import ScenarioSelector

class TestScenarioSelector:
    def test_init(self):
        # Test initialization with a ScenarioList object
        scenarios = ScenarioList([Scenario({'test_1': 1, 'test_2': 2, 'other': 3})])
        selector = ScenarioSelector(scenarios)
        assert selector.scenario_list == scenarios
        assert set(selector.available_fields) == {'test_1', 'test_2', 'other'}
        
        # Test with empty ScenarioList
        empty_scenarios = ScenarioList([])
        empty_selector = ScenarioSelector(empty_scenarios)
        assert empty_selector.available_fields == []

    def test_match_field_pattern(self):
        scenarios = ScenarioList([Scenario({'test_1': 1, 'test_2': 2, 'other': 3})])
        selector = ScenarioSelector(scenarios)
        
        # Exact match
        assert selector._match_field_pattern('test_1', 'test_1') is True
        assert selector._match_field_pattern('test_1', 'test_2') is False
        
        # Wildcard at start
        assert selector._match_field_pattern('*_1', 'test_1') is True
        assert selector._match_field_pattern('*_1', 'test_2') is False
        
        # Wildcard at end
        assert selector._match_field_pattern('test*', 'test_1') is True
        assert selector._match_field_pattern('test*', 'other') is False
        
        # Wildcard at both ends
        assert selector._match_field_pattern('*est*', 'test_1') is True
        assert selector._match_field_pattern('*123*', 'test_1') is False

    def test_get_matching_fields(self):
        scenarios = ScenarioList([Scenario({'test_1': 1, 'test_2': 2, 'other': 3})])
        selector = ScenarioSelector(scenarios)
        
        # Single pattern
        assert set(selector._get_matching_fields(['test*'])) == {'test_1', 'test_2'}
        assert set(selector._get_matching_fields(['*_1'])) == {'test_1'}
        
        # Multiple patterns
        assert set(selector._get_matching_fields(['test*', 'other'])) == {'test_1', 'test_2', 'other'}
        
        # No matches
        assert selector._get_matching_fields(['nonexistent*']) == []

    def test_select(self):
        scenarios = ScenarioList([
            Scenario({'test_1': 1, 'test_2': 2, 'other': 3}),
            Scenario({'test_1': 4, 'test_2': 5, 'other': 6})
        ])
        selector = ScenarioSelector(scenarios)
        
        # Select with wildcard pattern
        result = selector.select('test*')
        assert len(result) == 2
        assert result[0] == Scenario({'test_1': 1, 'test_2': 2})
        assert result[1] == Scenario({'test_1': 4, 'test_2': 5})
        
        # Select with exact field name
        result = selector.select('other')
        assert len(result) == 2
        assert result[0] == Scenario({'other': 3})
        assert result[1] == Scenario({'other': 6})
        
        # Select with multiple patterns
        result = selector.select('test_1', 'other')
        assert len(result) == 2
        assert result[0] == Scenario({'test_1': 1, 'other': 3})
        assert result[1] == Scenario({'test_1': 4, 'other': 6})
        
        # Error when no fields match
        with pytest.raises(ValueError, match="No fields matched the given patterns"):
            selector.select('nonexistent')
        
        # Test with empty ScenarioList
        empty_selector = ScenarioSelector(ScenarioList([]))
        assert empty_selector.select('test*') == ScenarioList([])

    def test_get_available_fields(self):
        scenarios = ScenarioList([Scenario({'test_1': 1, 'test_2': 2, 'other': 3})])
        selector = ScenarioSelector(scenarios)
        
        # Fields should be returned in sorted order
        assert selector.get_available_fields() == ['other', 'test_1', 'test_2']
        
        # Test with empty ScenarioList
        empty_selector = ScenarioSelector(ScenarioList([]))
        assert empty_selector.get_available_fields() == []


if __name__ == "__main__":
    pytest.main()