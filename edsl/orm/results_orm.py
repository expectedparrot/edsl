"""SQLAlchemy ORM models for the Result and Results domain objects.

This module provides SQLAlchemy ORM models for persisting Result and Results
objects to a database. It includes models for storing individual interview results
and collections of results, along with functions for saving, loading, and managing
these objects in the database.
"""

from __future__ import annotations
import json
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, Type

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Table, Boolean, JSON
from sqlalchemy.orm import relationship, Session, backref, Mapped, mapped_column
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import configure_mappers

# Import the shared Base
#from ..base.sql_model_base import Base
#from .sql_model_base import Base
from .sql_base import Base

# Import domain models for conversion
from ..results import Result
from ..results import Results
from ..base.exceptions import BaseException
from ..language_models import LanguageModel
# ..agents import Agent # Not directly used here anymore for type hint
from ..scenarios import Scenario
from ..surveys import Survey
from ..prompts import Prompt # Assuming this is the correct path for Prompt

# Import MappedObject types for relationships in from_edsl_object methods
from edsl.orm.agents_orm import AgentMappedObject
from edsl.orm.scenarios_orm import ScenarioMappedObject
from edsl.orm.language_models_orm import LanguageModelMappedObject
from edsl.orm.surveys_orm import SurveyMappedObject


class ResultsOrmException(BaseException):
    """Exception raised for errors in the Result ORM operations."""
    pass


# Removed old Table definition for results_collection_result_association
# It will be defined by the ResultCollectionAssociation ORM class below.

class ResultCollectionAssociation(Base):
    __tablename__ = "results_collection_result_association"
    edsl_class = None
    results_collection_id: Mapped[int] = mapped_column(ForeignKey("results.id", ondelete="CASCADE"), primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("result.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships to the parent tables
    results_collection: Mapped["ResultsMappedObject"] = relationship(back_populates="result_links")
    result: Mapped["ResultMappedObject"] = relationship(back_populates="collection_links")

    def __repr__(self):
        return f"<ResultCollectionAssociation(collection_id={self.results_collection_id}, result_id={self.result_id}, pos={self.position})>"


class ResultDataMappedObject(Base): # Renamed class
    """SQLAlchemy ORM model for storing key-value pairs of a Result's data."""
    
    __tablename__ = "result_data" # Table name is already singular
    edsl_class = None
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("result.id", ondelete="CASCADE")) # nullable=False is implied by Mapped[int]
    data_type: Mapped[str] = mapped_column(String(255)) # nullable=False is implied
    key: Mapped[str] = mapped_column(String(255)) # nullable=False is implied
    value_type: Mapped[str] = mapped_column(String(50)) # nullable=False is implied
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationship to parent Result
    result: Mapped["ResultMappedObject"] = relationship(back_populates="data_entries") # Renamed class
    
    # Relationship to ResultsMappedObject (many-to-many) - replaced by association object
    # parent_results_collections: Mapped[List["ResultsMappedObject"]] = relationship(
    #     secondary=results_collection_result_association,
    #     back_populates="results"
    # )
    
    def __repr__(self) -> str:
        """Return string representation of the ResultData."""
        return f"<ResultDataMappedObject(id={self.id}, result_id={self.result_id}, data_type='{self.data_type}', key='{self.key}')>" # Renamed class


class ResultMappedObject(Base): # Renamed class
    """SQLAlchemy ORM model for Result metadata."""
    
    __tablename__ = "result" # Renamed table
    edsl_class = Result
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("agent.id", use_alter=True, name="fk_result_agent_id"), nullable=True)
    scenario_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("scenario.id", use_alter=True, name="fk_result_scenario_id"), nullable=True)
    model_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("language_model.id", use_alter=True, name="fk_result_model_id"), nullable=True)
    iteration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interview_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    data_entries: Mapped[List["ResultDataMappedObject"]] = relationship(back_populates="result", cascade="all, delete-orphan")
    
    # Relationships to Agent, Scenario, Model Mapped Objects
    agent: Mapped[Optional["AgentMappedObject"]] = relationship(foreign_keys=[agent_id], cascade="save-update, merge, expunge")
    scenario: Mapped[Optional["ScenarioMappedObject"]] = relationship(foreign_keys=[scenario_id], cascade="save-update, merge, expunge")
    model: Mapped[Optional["LanguageModelMappedObject"]] = relationship(foreign_keys=[model_id], cascade="save-update, merge, expunge")

    collection_links: Mapped[List["ResultCollectionAssociation"]] = relationship(
        back_populates="result", cascade="all, delete-orphan"
    )
    parent_results_collections: Mapped[List["ResultsMappedObject"]] = association_proxy(
        "collection_links", "results_collection"
    )

    def __repr__(self) -> str:
        """Return string representation of the Result."""
        return f"<ResultMappedObject(id={self.id}, agent_id={self.agent_id}, scenario_id={self.scenario_id}, model_id={self.model_id})>"
    
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
        elif isinstance(value, Prompt): # Handle Prompt objects
            return 'prompt_text', value.text # Assuming Prompt has a .text attribute
        elif isinstance(value, dict):
            try:
                return 'json', json.dumps(value)
            except:
                # If not JSON serializable, fall back to pickle
                return f'pickle:dict', pickle.dumps(value).hex()
        elif isinstance(value, list):
            try:
                return 'json_list', json.dumps(value)
            except:
                # If not JSON serializable, fall back to pickle
                return f'pickle:list', pickle.dumps(value).hex()
        else:
            # For complex types, use pickle
            try:
                serialized = pickle.dumps(value).hex()
                return f'pickle:{type(value).__name__}', serialized
            except Exception as e:
                raise ResultsOrmException(f"Could not serialize value of type {type(value)}: {e}")
    
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
            elif value_type == 'prompt_text': # Handle Prompt objects
                return Prompt(text=value_text) # Assuming Prompt can be reconstructed this way
            elif value_type == 'json':
                return json.loads(value_text)
            elif value_type == 'json_list':
                return json.loads(value_text)
            elif value_type.startswith('pickle:'):
                try:
                    return pickle.loads(bytes.fromhex(value_text))
                except Exception as e:
                    raise ResultsOrmException(f"Could not deserialize pickled value: {e}")
            else:
                raise ResultsOrmException(f"Unknown value type: {value_type}")
        except Exception as e:
            print(f"Error deserializing value of type {value_type}: {e}")
            return None
    
    def to_edsl_object(self) -> Result:
        """Convert this ORM model to a Result domain object.
        Assumes related objects (agent, scenario, model) are loaded if needed.
        """
        # Create data structure to hold all the result data
        data_from_entries = {
            "answer": {}, "prompt": {}, "raw_model_response": {},
            "generated_tokens": {}, "comments_dict": {}, "cache_used_dict": {},
            "cache_keys": {}, "question_to_attributes": {},
        }
        
        # Extract all data entries and organize by data_type
        for entry in self.data_entries:
            value = self.deserialize_value(entry.value_type, entry.value_text)
            if entry.data_type not in data_from_entries: # Should not happen if data is well-formed
                data_from_entries[entry.data_type] = {}
            data_from_entries[entry.data_type][entry.key] = value
        
        # Convert related ORM objects to EDSL domain objects
        # Assumes self.agent, self.scenario, self.model are populated (e.g., eagerly loaded)
        agent_domain = self.agent.to_edsl_object() if self.agent else None
        scenario_domain = self.scenario.to_edsl_object() if self.scenario else None
        model_domain = self.model.to_edsl_object() if self.model else None
        
        # Extract indices if available
        # Uses the IDs stored in the ResultMappedObject itself
        indices = None
        if all([self.agent_id, self.scenario_id, self.model_id]):
            indices = {
                "agent": self.agent_id,
                "scenario": self.scenario_id,
                "model": self.model_id
            }
        
        # Create Result object using data from entries and converted domain objects
        result_edsl = Result(
            agent=agent_domain,
            scenario=scenario_domain,
            model=model_domain,
            iteration=self.iteration,
            answer=data_from_entries.get("answer", {}),
            prompt=data_from_entries.get("prompt", {}),
            raw_model_response=data_from_entries.get("raw_model_response", {}),
            question_to_attributes=data_from_entries.get("question_to_attributes", {}),
            generated_tokens=data_from_entries.get("generated_tokens", {}),
            comments_dict=data_from_entries.get("comments_dict", {}),
            cache_used_dict=data_from_entries.get("cache_used_dict", {}),
            indices=indices, # Uses IDs
            cache_keys=data_from_entries.get("cache_keys", {})
        )
        
        # Add interview hash if it exists
        if self.interview_hash:
            result_edsl.interview_hash = self.interview_hash
            
        # Add order if it exists
        if self.order is not None:
            result_edsl.order = self.order
        
        # Assign the ORM id to the edsl object for tracking
        result_edsl._orm_id = self.id

        return result_edsl
    
    @classmethod
    def from_edsl_object(cls, result_edsl: Result) -> "ResultMappedObject":
        """Create a new, detached ORM model from a Result domain object.
        Does not interact with the database session.
        """
        orm_result = cls(
            iteration=result_edsl.data.get("iteration", 0), # Reverted: iteration is in data dict
            interview_hash=getattr(result_edsl, "interview_hash", None),
            order=getattr(result_edsl, "order", None) 
        )
        
        # Create and assign related ORM objects if they exist in the EDSL object
        if result_edsl.agent:
            orm_result.agent = AgentMappedObject.from_edsl_object(result_edsl.agent)
        
        if result_edsl.scenario:
            orm_result.scenario = ScenarioMappedObject.from_edsl_object(result_edsl.scenario)
            
        if result_edsl.model:
            orm_result.model = LanguageModelMappedObject.from_edsl_object(result_edsl.model)
        
        # Process all data entries. These will be new, detached ResultDataMappedObject instances.
        # They will be associated with orm_result via the relationship and persisted by cascade
        # when orm_result is added to a session by the caller.
        orm_result.data_entries = []
        for data_type, data_dict in result_edsl.data.items():
            if isinstance(data_dict, dict):
                for key, value in data_dict.items():
                    value_type_str, value_text_str = cls.serialize_value(value)
                    data_entry_orm = ResultDataMappedObject(
                        # result_id will be set by SQLAlchemy relationship/cascade
                        data_type=data_type,
                        key=key,
                        value_type=value_type_str,
                        value_text=value_text_str
                    )
                    orm_result.data_entries.append(data_entry_orm)
        
        return orm_result


class ResultsMappedObject(Base): # Renamed class
    """SQLAlchemy ORM model for Results collections."""
    
    __tablename__ = "results" # Renamed table
    edsl_class = Results
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    survey_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("survey.id", use_alter=True, name="fk_results_collection_survey_id"), nullable=True) # Reference to survey in Survey table
    created_columns: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Store as JSON
    job_uuid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_results: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=True) # nullable=False implied by Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    result_links: Mapped[List["ResultCollectionAssociation"]] = relationship(
        back_populates="results_collection", 
        cascade="all, delete-orphan", 
        order_by="ResultCollectionAssociation.position"
    )
    results = association_proxy("result_links", "result", 
                                creator=lambda result_obj: ResultCollectionAssociation(result=result_obj))

    survey: Mapped[Optional["SurveyMappedObject"]] = relationship(foreign_keys=[survey_id], cascade="save-update, merge, expunge")
    
    def __repr__(self) -> str:
        """Return string representation of the Results."""
        return f"<ResultsMappedObject(id={self.id}, survey_id={self.survey_id}, results_count={len(self.results) if self.results else 0})>"
    
    def to_edsl_object(self) -> Results:
        """Convert this ORM model to a Results domain object.
        Assumes related survey and result objects are loaded if needed.
        """
        survey_domain = self.survey.to_edsl_object() if self.survey else None
        
        # Convert created_columns from JSON string to list
        created_columns_list = json.loads(self.created_columns) if self.created_columns else []
        
        # Convert all ResultMappedObject objects to EDSL Result objects via the association
        results_data_domain = [link.result.to_edsl_object() for link in self.result_links]
        
        # Create the EDSL Results object
        results_edsl = Results(
            survey=survey_domain,
            data=results_data_domain,
            created_columns=created_columns_list,
            job_uuid=self.job_uuid, # Direct attribute
            total_results=self.total_results # Direct attribute
        )
        
        # Copy completion status and ORM ID
        results_edsl.completed = self.completed
        results_edsl._orm_id = self.id
        
        return results_edsl
    
    @classmethod
    def from_edsl_object(cls, results_edsl: Results) -> "ResultsMappedObject":
        """Create a new, detached ORM model from a Results domain object.
        Does not interact with the database session.
        """
        
        # Create the base ORM record
        orm_results = cls(
            # survey_id will be handled by relationship cascade
            created_columns=json.dumps(results_edsl.created_columns) if results_edsl.created_columns else None,
            job_uuid=getattr(results_edsl, "_job_uuid", None), # Use getattr for potentially private attributes
            total_results=getattr(results_edsl, "_total_results", None),
            completed=results_edsl.completed
        )

        if results_edsl.survey:
            orm_results.survey = SurveyMappedObject.from_edsl_object(results_edsl.survey)
        
        # Convert EDSL Result objects to ResultMappedObject and add to the relationship collection
        # through the association proxy, or by creating association objects directly.
        orm_results.result_links = [] # Initialize the list for association objects
        if results_edsl.data:
            for i, result_domain_object in enumerate(results_edsl.data):
                result_orm_object = ResultMappedObject.from_edsl_object(result_domain_object)
                # Create the association object explicitly and add it to result_links
                association = ResultCollectionAssociation(
                    result=result_orm_object, 
                    position=i
                    # results_collection will be implicitly set by SQLAlchemy 
                    # when this association is appended to orm_results.result_links
                )
                orm_results.result_links.append(association)
                # If using the association_proxy with a creator that handles position, this might be simpler:
                # orm_results.results.append(result_orm_object) # and creator sets position
                # However, explicit creation of association object gives full control here.
        
        return orm_results

configure_mappers() # Explicitly configure all mappers once all classes are defined

if __name__ == "__main__":
    from edsl.orm.sql_base import create_test_session
    from edsl.results import Results, Result # EDSL Results class
    # EDSL domain objects are implicitly handled by Results.example()
    # from edsl.agents import Agent
    # from edsl.scenarios import Scenario
    # from edsl.language_models import LanguageModel
    # from edsl.surveys import Survey
    
    # MappedObject classes are imported globally now if needed by ORM class methods,
    # or can be re-imported here if preferred for test scope.
    # from edsl.orm.agents_orm import AgentMappedObject
    # from edsl.orm.scenarios_orm import ScenarioMappedObject 
    # from edsl.orm.language_models_orm import LanguageModelMappedObject
    # from edsl.orm.surveys_orm import SurveyMappedObject

    # Create a new test database session
    db_session, engine, BaseRelation = create_test_session()

    # Test Result ORM

    example_result_edsl = Result.example()

    result_mapped_obj = ResultMappedObject.from_edsl_object(example_result_edsl)
    db_session.add(result_mapped_obj)
    db_session.commit()
    retrieved_id = result_mapped_obj.id
    db_session.expire_all() 


    example_results_edsl = Results.example()
    example_results_edsl = Results.pull("f7a2aa22-6958-418e-bbf4-27b77a01ff7f")

    results_mapped_obj = ResultsMappedObject.from_edsl_object(example_results_edsl)
    db_session.add(results_mapped_obj)  
    db_session.commit()
    retrieved_id = results_mapped_obj.id
    db_session.expire_all() 


    db_session.close()

