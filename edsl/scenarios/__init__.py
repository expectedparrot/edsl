"""
The scenarios package provides tools for creating and managing parameterized templates.

This package is a core component of EDSL that enables parameterized content through
key-value dictionaries called Scenarios. These Scenarios can be used to provide variable
content to questions, surveys, and other components within EDSL.

Key components:
- Scenario: A dictionary-like object for storing key-value pairs to parameterize questions
- ScenarioList: A collection of Scenario objects with powerful data manipulation capabilities
- FileStore: A specialized Scenario subclass for handling files of various formats

The scenarios package supports various file formats, data sources, and transformations,
enabling complex experimental designs and data-driven surveys.

Example:
    >>> from edsl.scenarios import Scenario, ScenarioList
    >>> # Create a simple scenario
    >>> s1 = Scenario({"product": "coffee", "price": 4.99})
    >>> s2 = Scenario({"product": "tea", "price": 3.50})
    >>> # Create a scenario list
    >>> sl = ScenarioList([s1, s2])
    >>> # Use scenarios to parameterize questions and surveys
"""

from .scenario import Scenario
from .scenario_list import ScenarioList
from .scenario_serializer import ScenarioSerializer
from .scenario_factory import ScenarioFactory
from .scenario_gcs import ScenarioGCS
from .scenario_offloader import ScenarioOffloader
from .scenario_selector import ScenarioSelector
from .file_store import FileStore
from .file_store_list import FileStoreList
from .dimension import Dimension, DimensionValue
from .conjoint_profile_generator import ConjointProfileGenerator
from .agent_blueprint import AgentBlueprint

__all__ = ["Scenario", "ScenarioList", "ScenarioSerializer", "ScenarioFactory", "ScenarioGCS", "ScenarioOffloader", "ScenarioSelector", "FileStore", "FileStoreList", "Dimension", "DimensionValue", "ConjointProfileGenerator", "AgentBlueprint"]
