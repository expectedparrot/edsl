"""SQLAlchemy ORM models for the Scenario and ScenarioList domain objects.

This module provides SQLAlchemy ORM models for persisting Scenario and ScenarioList 
objects to a database. It includes models for storing the key-value structure of 
Scenarios and the collection structure of ScenarioList, along with functions for
saving, loading, and managing these objects in the database.
"""

from __future__ import annotations
import json
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Type

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, backref

# Create base class for declarative models
Base = declarative_base()

# Import domain models for conversion
from .scenario import Scenario
from .scenario_list import ScenarioList
from .file_store import FileStore
from ..base.exceptions import BaseException


class ScenarioOrmException(BaseException):
    """Exception raised for errors in the Scenario ORM operations."""
    pass


# Many-to-many relationship between ScenarioList and Scenario
scenario_list_scenario_association = Table(
    "scenario_list_scenario_association",
    Base.metadata,
    Column("scenario_list_id", Integer, ForeignKey("scenario_lists.id", ondelete="CASCADE"), primary_key=True),
    Column("scenario_id", Integer, ForeignKey("scenarios.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, nullable=False)  # To maintain scenario order
)


class SQLScenarioKeyValue(Base):
    """SQLAlchemy ORM model for storing key-value pairs of a Scenario."""
    
    __tablename__ = "scenario_key_values"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(255), nullable=False)
    value_type = Column(String(50), nullable=False)  # Type of the value (str, int, dict, etc.)
    value_text = Column(Text, nullable=True)  # For string values or serialized objects
    
    # Relationship to parent Scenario
    scenario = relationship("SQLScenario", back_populates="key_values")
    
    def __repr__(self) -> str:
        """Return string representation of the ScenarioKeyValue."""
        return f"<SQLScenarioKeyValue(id={self.id}, scenario_id={self.scenario_id}, key='{self.key}')>"


class SQLScenario(Base):
    """SQLAlchemy ORM model for Scenario metadata."""
    
    __tablename__ = "scenarios"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    key_values = relationship("SQLScenarioKeyValue", back_populates="scenario", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        """Return string representation of the Scenario."""
        return f"<SQLScenario(id={self.id}, name={self.name})>"
    
    @staticmethod
    def serialize_value(value: Any) -> tuple[str, str]:
        """Serialize a value for storage in the database."""
        if value is None:
            return 'null', 'null'
        elif isinstance(value, bool):  # Check for bool before int (bool is a subclass of int)
            return 'bool', str(value).lower()
        elif isinstance(value, str):
            return 'str', value
        elif isinstance(value, int):
            return 'int', str(value)
        elif isinstance(value, float):
            return 'float', str(value)
        elif isinstance(value, FileStore):
            # Handle FileStore specially
            return 'filestore', json.dumps(value.to_dict())
        else:
            # For complex types, use pickle
            try:
                serialized = pickle.dumps(value).hex()
                return f'pickle:{type(value).__name__}', serialized
            except Exception as e:
                raise ScenarioOrmException(f"Could not serialize value of type {type(value)}: {e}")
    
    @staticmethod
    def deserialize_value(value_type: str, value_text: str) -> Any:
        """Deserialize a value from storage."""
        try:
            if value_type == 'null':
                return None
            elif value_type == 'str':
                return value_text
            elif value_type == 'int':
                return int(value_text)
            elif value_type == 'float':
                return float(value_text)
            elif value_type == 'bool':
                return value_text.lower() == 'true'
            elif value_type == 'filestore':
                return FileStore.from_dict(json.loads(value_text))
            elif value_type.startswith('pickle:'):
                try:
                    return pickle.loads(bytes.fromhex(value_text))
                except Exception as e:
                    raise ScenarioOrmException(f"Could not deserialize pickled value: {e}")
            else:
                raise ScenarioOrmException(f"Unknown value type: {value_type}")
        except Exception as e:
            print(f"Error deserializing value of type {value_type}: {e}")
            return None
    
    def to_scenario(self) -> Scenario:
        """Convert this ORM model to a Scenario domain object."""
        data = {}
        
        # Convert all key-values to a dictionary
        for kv in self.key_values:
            value = self.deserialize_value(kv.value_type, kv.value_text)
            if value is not None:  # Skip None values due to deserialization errors
                data[kv.key] = value
        
        return Scenario(data=data, name=self.name)
    
    @classmethod
    def from_scenario(cls, scenario: Scenario, session: Optional[Session] = None) -> SQLScenario:
        """Create an ORM model from a Scenario domain object."""
        orm_scenario = cls(name=scenario.name)
        
        # Add each key-value pair
        for key, value in scenario.items():
            value_type, value_text = cls.serialize_value(value)
            kv = SQLScenarioKeyValue(
                key=key,
                value_type=value_type,
                value_text=value_text
            )
            orm_scenario.key_values.append(kv)
        
        if session:
            session.add(orm_scenario)
            session.flush()
        
        return orm_scenario


class SQLScenarioList(Base):
    """SQLAlchemy ORM model for ScenarioList."""
    
    __tablename__ = "scenario_lists"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    codebook_json = Column(Text, nullable=True)  # Store codebook as JSON
    
    # Relationships
    scenarios = relationship(
        "SQLScenario", 
        secondary=scenario_list_scenario_association,
        order_by=scenario_list_scenario_association.c.position,
        backref=backref("scenario_lists", lazy="dynamic")
    )
    
    def __repr__(self) -> str:
        """Return string representation of the ScenarioList."""
        return f"<SQLScenarioList(id={self.id}, scenarios_count={len(self.scenarios) if self.scenarios else 0})>"
    
    @property
    def codebook(self) -> Optional[Dict[str, str]]:
        """Get the codebook dictionary."""
        if self.codebook_json:
            return json.loads(self.codebook_json)
        return None
    
    @codebook.setter
    def codebook(self, value: Optional[Dict[str, str]]):
        """Set the codebook dictionary."""
        if value:
            self.codebook_json = json.dumps(value)
        else:
            self.codebook_json = None
    
    def to_scenario_list(self) -> ScenarioList:
        """Convert this ORM model to a ScenarioList domain object."""
        # Convert all scenarios
        scenarios = [s.to_scenario() for s in self.scenarios]
        
        return ScenarioList(data=scenarios, codebook=self.codebook)
    
    @classmethod
    def from_scenario_list(cls, scenario_list: ScenarioList, session: Session) -> SQLScenarioList:
        """Create an ORM model from a ScenarioList domain object."""
        # Create with codebook
        orm_list = cls()
        orm_list.codebook = scenario_list.codebook if hasattr(scenario_list, 'codebook') else None
        
        # Add to session to get ID
        session.add(orm_list)
        session.flush()
        
        # Add each scenario with position
        for i, scenario in enumerate(scenario_list):
            # Check if scenario already exists in database
            scenario_orm = None
            if hasattr(scenario, '_orm_id') and scenario._orm_id:
                scenario_orm = session.query(SQLScenario).get(scenario._orm_id)
            
            # Create new scenario ORM if needed
            if not scenario_orm:
                scenario_orm = SQLScenario.from_scenario(scenario, session)
            
            # Add association with position
            stmt = scenario_list_scenario_association.insert().values(
                scenario_list_id=orm_list.id,
                scenario_id=scenario_orm.id,
                position=i
            )
            session.execute(stmt)
        
        return orm_list


def save_scenario(session: Session, scenario: Scenario) -> SQLScenario:
    """Save a Scenario to the database."""
    # Check if the scenario already exists
    if hasattr(scenario, '_orm_id') and scenario._orm_id:
        # Try to update the existing scenario
        update_success = update_scenario(session, scenario._orm_id, scenario)
        if update_success:
            # Get the updated scenario
            scenario_orm = session.query(SQLScenario).get(scenario._orm_id)
            return scenario_orm
    
    # Create new scenario (or recreate if update failed)
    scenario_orm = SQLScenario.from_scenario(scenario)
    session.add(scenario_orm)
    session.flush()
    
    # Store the ORM ID in the domain object for future reference
    scenario._orm_id = scenario_orm.id
    
    return scenario_orm


def save_scenario_list(session: Session, scenario_list: ScenarioList) -> SQLScenarioList:
    """Save a ScenarioList to the database."""
    # Check if the scenario list already exists
    scenario_list_orm = None
    if hasattr(scenario_list, '_orm_id') and scenario_list._orm_id:
        scenario_list_orm = session.query(SQLScenarioList).get(scenario_list._orm_id)
    
    if scenario_list_orm:
        # Update existing scenario list
        scenario_list_orm.codebook = scenario_list.codebook if hasattr(scenario_list, 'codebook') else None
        
        # Clear existing associations
        stmt = scenario_list_scenario_association.delete().where(
            scenario_list_scenario_association.c.scenario_list_id == scenario_list_orm.id
        )
        session.execute(stmt)
    else:
        # Create new scenario list
        scenario_list_orm = SQLScenarioList()
        scenario_list_orm.codebook = scenario_list.codebook if hasattr(scenario_list, 'codebook') else None
        session.add(scenario_list_orm)
        session.flush()
    
    # We need to save scenarios before adding associations
    saved_scenario_orms = []
    
    # Add each scenario with position
    for i, scenario in enumerate(scenario_list):
        # Check if the scenario already exists in the database
        if hasattr(scenario, '_orm_id') and scenario._orm_id:
            # Update existing scenario
            update_success = update_scenario(session, scenario._orm_id, scenario)
            if update_success:
                # Get the updated scenario
                scenario_orm = session.query(SQLScenario).get(scenario._orm_id)
            else:
                # Create a new scenario if update failed
                scenario_orm = SQLScenario.from_scenario(scenario, session)
        else:
            # Create a new scenario
            scenario_orm = SQLScenario.from_scenario(scenario, session)
            session.add(scenario_orm)
            session.flush()
            # Store the ORM ID in the domain object
            scenario._orm_id = scenario_orm.id
        
        saved_scenario_orms.append(scenario_orm)
    
    # Now add all associations
    for i, scenario_orm in enumerate(saved_scenario_orms):
        # Add association with position
        stmt = scenario_list_scenario_association.insert().values(
            scenario_list_id=scenario_list_orm.id,
            scenario_id=scenario_orm.id,
            position=i
        )
        session.execute(stmt)
    
    # Store the ORM ID in the domain object for future reference
    scenario_list._orm_id = scenario_list_orm.id
    
    return scenario_list_orm


def update_scenario(session: Session, scenario_id: int, scenario: Scenario) -> bool:
    """Update an existing scenario in the database."""
    scenario_orm = session.query(SQLScenario).get(scenario_id)
    if not scenario_orm:
        return False
    
    # Update name
    scenario_orm.name = scenario.name
    
    # Delete existing key-values
    for kv in list(scenario_orm.key_values):
        session.delete(kv)
    
    # Add new key-values
    for key, value in scenario.items():
        value_type, value_text = SQLScenario.serialize_value(value)
        kv = SQLScenarioKeyValue(
            scenario_id=scenario_id,
            key=key,
            value_type=value_type,
            value_text=value_text
        )
        session.add(kv)
    
    return True


def load_scenario(session: Session, scenario_id: int) -> Optional[Scenario]:
    """Load a Scenario from the database by ID."""
    scenario_orm = session.query(SQLScenario).get(scenario_id)
    if scenario_orm:
        scenario = scenario_orm.to_scenario()
        scenario._orm_id = scenario_orm.id
        return scenario
    return None


def load_scenario_list(session: Session, scenario_list_id: int) -> Optional[ScenarioList]:
    """Load a ScenarioList from the database by ID."""
    scenario_list_orm = session.query(SQLScenarioList).get(scenario_list_id)
    if scenario_list_orm:
        scenario_list = scenario_list_orm.to_scenario_list()
        scenario_list._orm_id = scenario_list_orm.id
        
        # Set the _orm_id on each scenario
        for i, scenario_orm in enumerate(scenario_list_orm.scenarios):
            if i < len(scenario_list):
                scenario_list[i]._orm_id = scenario_orm.id
        
        return scenario_list
    return None


def delete_scenario(session: Session, scenario_id: int) -> bool:
    """Delete a Scenario from the database."""
    scenario_orm = session.query(SQLScenario).get(scenario_id)
    if scenario_orm:
        session.delete(scenario_orm)
        return True
    return False


def delete_scenario_list(session: Session, scenario_list_id: int) -> bool:
    """Delete a ScenarioList from the database."""
    scenario_list_orm = session.query(SQLScenarioList).get(scenario_list_id)
    if scenario_list_orm:
        session.delete(scenario_list_orm)
        return True
    return False


def list_scenarios(session: Session, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List scenarios in the database with pagination."""
    scenarios = session.query(SQLScenario).order_by(SQLScenario.created_at.desc()) \
        .limit(limit).offset(offset).all()
    return [{"id": s.id, "name": s.name, "created_at": s.created_at} for s in scenarios]


def list_scenario_lists(session: Session, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List scenario lists in the database with pagination."""
    lists = session.query(SQLScenarioList).order_by(SQLScenarioList.created_at.desc()) \
        .limit(limit).offset(offset).all()
    return [{"id": l.id, "name": l.name, "created_at": l.created_at, 
             "scenario_count": len(l.scenarios)} for l in lists]


def print_sql_schema(engine):
    """Print the SQL schema for the scenario-related tables."""
    from sqlalchemy.schema import CreateTable
    
    print("\n--- SQL Schema for Scenario Tables ---")
    for table in [
        SQLScenario.__table__,
        SQLScenarioKeyValue.__table__,
        SQLScenarioList.__table__,
        scenario_list_scenario_association
    ]:
        print(f"\n-- Table: {table.name}")
        print(CreateTable(table).compile(engine))
    print("--- End of SQL Schema ---")