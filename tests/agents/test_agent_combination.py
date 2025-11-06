"""Test cases for agent combination functionality.

This module tests the behavior of combining agents using the + operator,
including proper handling of name and traits_presentation_template preservation.
"""

import warnings
from edsl.agents import Agent


class TestAgentCombination:
    """Test cases for agent combination functionality."""

    def test_name_preserved_from_first_agent(self):
        """Test that first agent's name is preserved when both have names."""
        a1 = Agent(name="Robin", traits={"firstname": "Robin", "age": 46})
        a2 = Agent(name="John", traits={"lastname": "Doe"})
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            a3 = a1 + a2
            
            # Should warn about name conflict
            assert len(w) == 1
            assert "Both agents have 'name' attributes" in str(w[0].message)
            assert "Robin" in str(w[0].message)
            assert "John" in str(w[0].message)
        
        assert a3.name == "Robin"

    def test_name_from_second_agent_when_first_has_none(self):
        """Test that second agent's name is used when first agent doesn't have one."""
        a1 = Agent(traits={"firstname": "Robin", "age": 46})
        a2 = Agent(name="John", traits={"lastname": "Doe"})
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            a3 = a1 + a2
            
            # Should not warn since there's no conflict
            assert len(w) == 0
        
        assert a3.name == "John"

    def test_traits_presentation_template_preserved_from_first(self):
        """Test that first agent's traits_presentation_template is preserved when both have custom templates."""
        a1 = Agent(traits={"age": 46}, traits_presentation_template="Boo!")
        a2 = Agent(traits={"height": 5.5}, traits_presentation_template="Hi")
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            a3 = a1 + a2
            
            # Should warn about template conflict
            assert len(w) == 1
            assert "Both agents have 'traits_presentation_template' attributes" in str(w[0].message)
        
        assert a3.traits_presentation_template == "Boo!"

    def test_traits_presentation_template_from_second_when_first_has_default(self):
        """Test that second agent's template is used when first has default."""
        a1 = Agent(traits={"firstname": "Robin", "age": 46})
        a2 = Agent(traits={"lastname": "Doe"}, traits_presentation_template="Hi")
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            a3 = a1 + a2
            
            # Should not warn since first agent has default template
            assert len(w) == 0
        
        assert a3.traits_presentation_template == "Hi"

    def test_both_name_and_template_conflicts(self):
        """Test warnings for both name and template conflicts simultaneously."""
        a1 = Agent(name="Robin", traits={"age": 46}, traits_presentation_template="Boo!")
        a2 = Agent(name="John", traits={"height": 5.5}, traits_presentation_template="Hi")
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            a3 = a1 + a2
            
            # Should warn about both conflicts
            assert len(w) == 2
            warning_messages = [str(warning.message) for warning in w]
            assert any("name" in msg for msg in warning_messages)
            assert any("traits_presentation_template" in msg for msg in warning_messages)
        
        assert a3.name == "Robin"
        assert a3.traits_presentation_template == "Boo!"

    def test_no_conflicts_no_warnings(self):
        """Test that no warnings are issued when there are no conflicts."""
        a1 = Agent(name="Robin", traits={"age": 46})
        a2 = Agent(traits={"height": 5.5}, traits_presentation_template="Hi")
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            a3 = a1 + a2
            
            # Should not warn since no conflicts
            assert len(w) == 0
        
        assert a3.name == "Robin"
        assert a3.traits_presentation_template == "Hi"

    def test_same_values_no_conflict(self):
        """Test that identical values don't trigger warnings."""
        a1 = Agent(name="John", traits={"age": 46}, traits_presentation_template="Hello")
        a2 = Agent(name="John", traits={"height": 5.5}, traits_presentation_template="Hello")
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            a3 = a1 + a2
            
            # Should not warn since values are identical
            assert len(w) == 0
        
        assert a3.name == "John"
        assert a3.traits_presentation_template == "Hello"

    def test_complex_combination_scenario_1(self):
        """Test complex agent combination with both name and template conflicts."""
        a1 = Agent(name="Robin", traits={"firstname": "Robin", "age": 46}, traits_presentation_template="Boo!")
        a2 = Agent(name="John", traits={"firstname": "John", "age": 47}, traits_presentation_template="Hi")
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            a3 = a1 + a2
            
            # Should warn about both conflicts
            assert len(w) == 2
            warning_messages = [str(warning.message) for warning in w]
            assert any("name" in msg and "Robin" in msg and "John" in msg for msg in warning_messages)
            assert any("traits_presentation_template" in msg for msg in warning_messages)
        
        # First agent's values should be preserved
        assert a3.name == "Robin"
        assert a3.traits_presentation_template == "Boo!"
        
        # Traits should be combined with conflict resolution
        assert a3.traits["firstname"] == "Robin"
        assert a3.traits["age"] == 46
        assert "firstname_1" in a3.traits
        assert a3.traits["firstname_1"] == "John"
        assert "age_1" in a3.traits
        assert a3.traits["age_1"] == 47

    def test_complex_combination_scenario_2(self):
        """Test agent combination where first agent lacks name and template."""
        a1 = Agent(traits={"firstname": "Robin", "age": 46})
        a2 = Agent(name="John", traits={"firstname": "John", "age": 47}, traits_presentation_template="Hi")
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            a3 = a1 + a2
            
            # Should not warn since first agent doesn't have name/template
            assert len(w) == 0
        
        # Second agent's values should be used since first doesn't have them
        assert a3.name == "John"
        assert a3.traits_presentation_template == "Hi"
        
        # Traits should still be combined with conflict resolution
        assert a3.traits["firstname"] == "Robin"
        assert a3.traits["age"] == 46
        assert "firstname_1" in a3.traits
        assert a3.traits["firstname_1"] == "John"
        assert "age_1" in a3.traits
        assert a3.traits["age_1"] == 47