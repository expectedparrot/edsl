from sqlalchemy import Column, Integer, Text, JSON, DateTime, func, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import Optional, Dict, Any, List
import tempfile
import os

from ..scenarios.scenario import Scenario
from ..scenarios.scenario_list import ScenarioList

from .sql_base import Base, TimestampMixin, UUIDTrackable


class ScenarioItem(Base):
    __tablename__ = "scenario_items"
    edsl_class = None
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario.id"))
    key: Mapped[str] = mapped_column()
    value: Mapped[Any] = mapped_column(JSON)  # Using JSON for flexibility in values

    scenario: Mapped["ScenarioMappedObject"] = relationship(back_populates="items")

    def __repr__(self):
        return f"ScenarioItem(id={self.id}, key='{self.key}', value='{self.value}')"


class ScenarioMappedObject(Base, TimestampMixin, UUIDTrackable):
    __tablename__ = "scenario"
    edsl_class = Scenario

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(nullable=True)
    
    items: Mapped[List["ScenarioItem"]] = relationship(
        "ScenarioItem", back_populates="scenario", cascade="all, delete-orphan"
    )
    
    # Foreign key and relationship for ScenarioList (if implemented)
    scenario_list_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("scenario_list.id"), nullable=True
    )
    scenario_list: Mapped[Optional["ScenarioListMappedObject"]] = relationship(
        back_populates="scenarios"
    )

    @classmethod
    def from_edsl_object(cls, edsl_object: 'Scenario'):
        """Converts an EDSL Scenario object into a ScenarioMappedObject ORM object."""
        # Get basic data without EDSL version info
        data = edsl_object.to_dict(add_edsl_version=False)
        
        # Create items from the scenario key-value pairs
        scenario_items = []
        for key, value in data.items():
            # Handle special cases like FileStore objects which are already serialized by to_dict
            scenario_items.append(ScenarioItem(key=key, value=value))
        
        return cls(
            name=edsl_object.name,
            items=scenario_items
        )
    
    def to_edsl_object(self) -> 'Scenario':
        """Converts the ORM object back to an EDSL Scenario object."""
        # Build the data dictionary from items
        data_dict = {item.key: item.value for item in self.items or []}
        
        # Import the Scenario class here to avoid circular imports
        from ..scenarios.scenario import Scenario
        
        # Create and return the Scenario instance
        return Scenario(data_dict, name=self.name)

    @classmethod
    def example(cls) -> 'ScenarioMappedObject':
        """Creates an example ScenarioMappedObject instance for testing"""
        from ..scenarios.scenario import Scenario
        return cls.from_edsl_object(Scenario.example())

    def __repr__(self) -> str:
        return f"ScenarioMappedObject(id={self.id}, name='{self.name}')"


class ScenarioListMappedObject(Base, TimestampMixin, UUIDTrackable):
    __tablename__ = "scenario_list"
    edsl_class = ScenarioList

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship to ScenarioMappedObject
    scenarios: Mapped[List["ScenarioMappedObject"]] = relationship(
        "ScenarioMappedObject",
        back_populates="scenario_list",
        cascade="all, delete-orphan"
    )

    @classmethod
    def from_edsl_object(cls, edsl_scenario_list: 'ScenarioList', name: Optional[str] = None) -> 'ScenarioListMappedObject':
        """Converts an EDSL ScenarioList object into a ScenarioListMappedObject ORM object."""
        mapped_scenarios = []
        if edsl_scenario_list.data:
            for scenario_edsl in edsl_scenario_list.data:
                scenario_mapped = ScenarioMappedObject.from_edsl_object(scenario_edsl)
                mapped_scenarios.append(scenario_mapped)
            
        return cls(name=name, scenarios=mapped_scenarios)

    def to_edsl_object(self) -> 'ScenarioList':
        """Converts this ScenarioListMappedObject ORM object back into an EDSL ScenarioList object."""
        from ..scenarios.scenario_list import ScenarioList
        
        scenario_list = ScenarioList()
        if self.scenarios:
            for scenario_mapped in self.scenarios:
                scenario_edsl = scenario_mapped.to_edsl_object()
                scenario_list.append(scenario_edsl)
        
        return scenario_list

    def __repr__(self) -> str:
        num_scenarios = len(self.scenarios) if self.scenarios else 0
        return f"ScenarioListMappedObject(id={self.id}, name='{self.name}', num_scenarios={num_scenarios})"


if __name__ == "__main__":
    from .sql_base import create_test_session, create_orm
    from ..scenarios.scenario import Scenario
    from ..scenarios.scenario_list import ScenarioList
    
    # Create a test session
    db, _, _ = create_test_session()
    
    # Test Scenario ORM
    test_scenario = Scenario({"product": "coffee", "price": 4.99}, name="Test Scenario")


    scenario_orm = create_orm(test_scenario)
    
    db.add(scenario_orm)
    db.commit()
    db.refresh(scenario_orm)
    
    print(f"Created scenario: {scenario_orm}")
    
    # Retrieve and verify
    retrieved_scenario_orm = db.query(ScenarioMappedObject).filter(ScenarioMappedObject.name == "Test Scenario").first()
    if retrieved_scenario_orm:
        print(f"Retrieved scenario: {retrieved_scenario_orm}")
        print(f"Created at: {retrieved_scenario_orm.created_at}")
        print("Items:")
        for item in retrieved_scenario_orm.items:
            print(f"  {item.key}: {item.value}")
    
    # Test ScenarioList ORM
    test_scenario_list = ScenarioList([
        Scenario({"product": "coffee", "price": 4.99}),
        Scenario({"product": "tea", "price": 3.99})
    ])

    test_scenario_list = ScenarioList.pull("278c5b51-26ae-41c6-8540-82ffb86d4a4a")
    
    scenario_list_orm = ScenarioListMappedObject.from_edsl_object(test_scenario_list, name="Test ScenarioList")
    db.add(scenario_list_orm)
    db.commit()
    db.refresh(scenario_list_orm)
    
    print(f"Created scenario list: {scenario_list_orm}")
    
    # Retrieve and verify
    retrieved_list_orm = db.query(ScenarioListMappedObject).filter(ScenarioListMappedObject.name == "Test ScenarioList").first()
    if retrieved_list_orm:
        print(f"Retrieved scenario list: {retrieved_list_orm}")
        print(f"Number of scenarios: {len(retrieved_list_orm.scenarios)}")
        
        # Convert back to EDSL object
        reconstituted_list = retrieved_list_orm.to_edsl_object()
        print(f"Reconstituted ScenarioList length: {len(reconstituted_list)}")
    
    db.close()