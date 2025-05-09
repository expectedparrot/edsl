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
from sqlalchemy.orm import relationship, Session, backref

# Import the shared Base
from ..base.sql_model_base import Base

# Import domain models for conversion
from .result import Result
from .results import Results
from ..base.exceptions import BaseException
from ..language_models import LanguageModel
from ..agents import Agent
from ..scenarios import Scenario
from ..surveys import Survey


class ResultsOrmException(BaseException):
    """Exception raised for errors in the Result ORM operations."""
    pass


# Many-to-many relationship between Results and Result
results_result_association = Table(
    "results_result_association",
    Base.metadata,
    Column("results_id", Integer, ForeignKey("results_collections.id", ondelete="CASCADE"), primary_key=True),
    Column("result_id", Integer, ForeignKey("results.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, nullable=False)  # To maintain result order
)


class SQLResultData(Base):
    """SQLAlchemy ORM model for storing key-value pairs of a Result's data."""
    
    __tablename__ = "result_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(Integer, ForeignKey("results.id", ondelete="CASCADE"), nullable=False)
    data_type = Column(String(255), nullable=False)  # answer, prompt, raw_model_response, etc.
    key = Column(String(255), nullable=False)
    value_type = Column(String(50), nullable=False)  # Type of the value (str, int, dict, etc.)
    value_text = Column(Text, nullable=True)  # For string values or serialized objects
    
    # Relationship to parent Result
    result = relationship("SQLResult", back_populates="data_entries")
    
    def __repr__(self) -> str:
        """Return string representation of the ResultData."""
        return f"<SQLResultData(id={self.id}, result_id={self.result_id}, data_type='{self.data_type}', key='{self.key}')>"


class SQLResult(Base):
    """SQLAlchemy ORM model for Result metadata."""
    
    __tablename__ = "results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, nullable=True)  # Reference to agent in Agent table
    scenario_id = Column(Integer, nullable=True)  # Reference to scenario in Scenario table
    model_id = Column(Integer, nullable=True)  # Reference to model in LanguageModel table
    iteration = Column(Integer, nullable=False, default=0)
    interview_hash = Column(String(255), nullable=True)
    order = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    data_entries = relationship("SQLResultData", back_populates="result", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        """Return string representation of the Result."""
        return f"<SQLResult(id={self.id}, agent_id={self.agent_id}, scenario_id={self.scenario_id}, model_id={self.model_id})>"
    
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
    
    def to_result(self, session: Session) -> Result:
        """Convert this ORM model to a Result domain object."""
        # Create data structure to hold all the result data
        data = {
            "answer": {},
            "prompt": {},
            "raw_model_response": {},
            "generated_tokens": {},
            "comments_dict": {},
            "cache_used_dict": {},
            "cache_keys": {},
            "question_to_attributes": {},
        }
        
        # Extract all data entries and organize by data_type
        for entry in self.data_entries:
            value = self.deserialize_value(entry.value_type, entry.value_text)
            
            if entry.data_type not in data:
                data[entry.data_type] = {}
                
            data[entry.data_type][entry.key] = value
        
        # Fetch the referenced objects from their respective tables
        from edsl.agents.orm import SQLAgent
        from edsl.scenarios.orm import SQLScenario
        from edsl.language_models.orm import SQLLanguageModel
        
        agent = session.query(SQLAgent).filter_by(id=self.agent_id).first().to_agent() if self.agent_id else None
        scenario = session.query(SQLScenario).filter_by(id=self.scenario_id).first().to_scenario() if self.scenario_id else None
        model = session.query(SQLLanguageModel).filter_by(id=self.model_id).first().to_model() if self.model_id else None
        
        # Extract indices if available
        indices = None
        if all([self.agent_id, self.scenario_id, self.model_id]):
            indices = {
                "agent": self.agent_id,
                "scenario": self.scenario_id,
                "model": self.model_id
            }
        
        # Create Result object
        result = Result(
            agent=agent,
            scenario=scenario,
            model=model,
            iteration=self.iteration,
            answer=data.get("answer", {}),
            prompt=data.get("prompt", {}),
            raw_model_response=data.get("raw_model_response", {}),
            question_to_attributes=data.get("question_to_attributes", {}),
            generated_tokens=data.get("generated_tokens", {}),
            comments_dict=data.get("comments_dict", {}),
            cache_used_dict=data.get("cache_used_dict", {}),
            indices=indices,
            cache_keys=data.get("cache_keys", {})
        )
        
        # Add interview hash if it exists
        if self.interview_hash:
            result.interview_hash = self.interview_hash
            
        # Add order if it exists
        if self.order is not None:
            result.order = self.order
        
        return result
    
    @classmethod
    def from_result(cls, result: Result, session: Session) -> SQLResult:
        """Create an ORM model from a Result domain object."""
        # Create the base record
        orm_result = cls(
            iteration=result.data.get("iteration", 0),
            interview_hash=getattr(result, "interview_hash", None),
            order=getattr(result, "order", None) 
        )
        
        # Store IDs of related objects
        # First check if the objects have _orm_id, which means they're already in the database
        if hasattr(result.agent, "_orm_id") and result.agent._orm_id:
            orm_result.agent_id = result.agent._orm_id
        else:
            # Save the Agent to the database if needed
            from edsl.agents.orm import SQLAgent
            agent_orm = SQLAgent.from_agent(result.agent, session)
            session.add(agent_orm)
            session.flush()
            orm_result.agent_id = agent_orm.id
            
        if hasattr(result.scenario, "_orm_id") and result.scenario._orm_id:
            orm_result.scenario_id = result.scenario._orm_id
        else:
            # Save the Scenario to the database if needed
            from edsl.scenarios.orm import SQLScenario
            scenario_orm = SQLScenario.from_scenario(result.scenario, session)
            session.add(scenario_orm)
            session.flush()
            orm_result.scenario_id = scenario_orm.id
            
        if hasattr(result.model, "_orm_id") and result.model._orm_id:
            orm_result.model_id = result.model._orm_id
        else:
            # Save the LanguageModel to the database if needed
            from edsl.language_models.orm import SQLLanguageModel
            model_orm = SQLLanguageModel.from_model(result.model, session)
            session.add(model_orm)
            session.flush()
            orm_result.model_id = model_orm.id
        
        # Add to session to get ID
        session.add(orm_result)
        session.flush()
        
        # Process all data entries
        for data_type, data_dict in result.data.items():
            if isinstance(data_dict, dict):
                for key, value in data_dict.items():
                    value_type, value_text = cls.serialize_value(value)
                    data_entry = SQLResultData(
                        result_id=orm_result.id,
                        data_type=data_type,
                        key=key,
                        value_type=value_type,
                        value_text=value_text
                    )
                    session.add(data_entry)
        
        return orm_result


class SQLResults(Base):
    """SQLAlchemy ORM model for Results collections."""
    
    __tablename__ = "results_collections"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    survey_id = Column(Integer, nullable=True)  # Reference to survey in Survey table
    created_columns = Column(Text, nullable=True)  # Store as JSON
    job_uuid = Column(String(255), nullable=True)
    total_results = Column(Integer, nullable=True)
    completed = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    results = relationship(
        "SQLResult", 
        secondary=results_result_association,
        order_by=results_result_association.c.position,
        backref=backref("results_collections", lazy="dynamic")
    )
    
    def __repr__(self) -> str:
        """Return string representation of the Results."""
        return f"<SQLResults(id={self.id}, results_count={len(self.results) if self.results else 0})>"
    
    def to_results(self, session: Session) -> Results:
        """Convert this ORM model to a Results domain object."""
        # Fetch the referenced Survey from its table
        from edsl.surveys.orm import SQLSurvey
        
        survey = None
        if self.survey_id:
            survey_orm = session.query(SQLSurvey).filter_by(id=self.survey_id).first()
            if survey_orm:
                survey = survey_orm.to_survey()
        
        # Convert created_columns from JSON string to list
        created_columns = json.loads(self.created_columns) if self.created_columns else []
        
        # Convert all Result objects
        results_data = [result_orm.to_result(session) for result_orm in self.results]
        
        # Create the Results
        results_obj = Results(
            survey=survey,
            data=results_data,
            created_columns=created_columns,
            job_uuid=self.job_uuid,
            total_results=self.total_results
        )
        
        # Copy completion status
        results_obj.completed = self.completed
        
        return results_obj
    
    @classmethod
    def from_results(cls, results_obj: Results, session: Session) -> SQLResults:
        """Create an ORM model from a Results domain object."""
        # Save the survey first if needed
        survey_id = None
        if results_obj.survey:
            if hasattr(results_obj.survey, "_orm_id") and results_obj.survey._orm_id:
                survey_id = results_obj.survey._orm_id
            else:
                from edsl.surveys.orm import SQLSurvey
                survey_orm = SQLSurvey.from_survey(results_obj.survey, session)
                session.add(survey_orm)
                session.flush()
                survey_id = survey_orm.id
        
        # Create the base record
        orm_results = cls(
            survey_id=survey_id,
            created_columns=json.dumps(results_obj.created_columns) if results_obj.created_columns else None,
            job_uuid=getattr(results_obj, "_job_uuid", None),
            total_results=getattr(results_obj, "_total_results", None),
            completed=results_obj.completed
        )
        
        # Add to session to get ID
        session.add(orm_results)
        session.flush()
        
        # Add each result with position
        for i, result in enumerate(results_obj.data):
            # Check if result already exists in database
            result_orm = None
            if hasattr(result, '_orm_id') and result._orm_id:
                result_orm = session.get(SQLResult, result._orm_id)
            
            # Create new result ORM if needed
            if not result_orm:
                result_orm = SQLResult.from_result(result, session)
            
            # Add association with position
            stmt = results_result_association.insert().values(
                results_id=orm_results.id,
                result_id=result_orm.id,
                position=i
            )
            session.execute(stmt)
        
        return orm_results


def save_result(session: Session, result: Result) -> SQLResult:
    """Save a Result to the database."""
    # Check if the result already exists
    if hasattr(result, '_orm_id') and result._orm_id:
        # Try to update the existing result
        update_success = update_result(session, result._orm_id, result)
        if update_success:
            # Get the updated result
            result_orm = session.get(SQLResult, result._orm_id)
            return result_orm
    
    # Create new result (or recreate if update failed)
    result_orm = SQLResult.from_result(result, session)
    session.add(result_orm)
    session.flush()
    
    # Store the ORM ID in the domain object for future reference
    result._orm_id = result_orm.id
    
    return result_orm


def update_result(session: Session, result_id: int, result: Result) -> bool:
    """Update an existing result in the database."""
    result_orm = session.get(SQLResult, result_id)
    if not result_orm:
        return False
    
    # Update basic attributes
    result_orm.iteration = result.data.get("iteration", 0)
    result_orm.interview_hash = getattr(result, "interview_hash", None)
    result_orm.order = getattr(result, "order", None)
    
    # Update references to agent, scenario, and model if changed
    if hasattr(result.agent, "_orm_id") and result.agent._orm_id:
        result_orm.agent_id = result.agent._orm_id
    
    if hasattr(result.scenario, "_orm_id") and result.scenario._orm_id:
        result_orm.scenario_id = result.scenario._orm_id
    
    if hasattr(result.model, "_orm_id") and result.model._orm_id:
        result_orm.model_id = result.model._orm_id
    
    # Delete existing data entries
    for entry in list(result_orm.data_entries):
        session.delete(entry)
    
    # Process all data entries
    for data_type, data_dict in result.data.items():
        if isinstance(data_dict, dict):
            for key, value in data_dict.items():
                value_type, value_text = SQLResult.serialize_value(value)
                data_entry = SQLResultData(
                    result_id=result_id,
                    data_type=data_type,
                    key=key,
                    value_type=value_type,
                    value_text=value_text
                )
                session.add(data_entry)
    
    return True


def save_results(session: Session, results_obj: Results) -> SQLResults:
    """Save a Results collection to the database."""
    # Check if the results collection already exists
    results_orm = None
    if hasattr(results_obj, '_orm_id') and results_obj._orm_id:
        results_orm = session.get(SQLResults, results_obj._orm_id)
    
    if results_orm:
        # Update existing results collection
        results_orm.completed = results_obj.completed
        
        if results_obj.survey and hasattr(results_obj.survey, "_orm_id"):
            results_orm.survey_id = results_obj.survey._orm_id
            
        results_orm.created_columns = json.dumps(results_obj.created_columns) if results_obj.created_columns else None
        results_orm.job_uuid = getattr(results_obj, "_job_uuid", None)
        results_orm.total_results = getattr(results_obj, "_total_results", None)
        
        # Clear existing associations
        stmt = results_result_association.delete().where(
            results_result_association.c.results_id == results_orm.id
        )
        session.execute(stmt)
    else:
        # Create new results collection
        results_orm = SQLResults.from_results(results_obj, session)
    
    # We need to save results before adding associations
    saved_result_orms = []
    
    # Add each result with position
    for i, result in enumerate(results_obj.data):
        # Save the result
        result_orm = save_result(session, result)
        saved_result_orms.append(result_orm)
    
    # Now add all associations
    for i, result_orm in enumerate(saved_result_orms):
        # Add association with position
        stmt = results_result_association.insert().values(
            results_id=results_orm.id,
            result_id=result_orm.id,
            position=i
        )
        session.execute(stmt)
    
    # Store the ORM ID in the domain object for future reference
    results_obj._orm_id = results_orm.id
    
    return results_orm


def load_result(session: Session, result_id: int) -> Optional[Result]:
    """Load a Result from the database by ID."""
    result_orm = session.get(SQLResult, result_id)
    if result_orm:
        result = result_orm.to_result(session)
        result._orm_id = result_orm.id
        return result
    return None


def load_results(session: Session, results_id: int) -> Optional[Results]:
    """Load a Results collection from the database by ID."""
    results_orm = session.get(SQLResults, results_id)
    if results_orm:
        results_obj = results_orm.to_results(session)
        results_obj._orm_id = results_orm.id
        
        # Set the _orm_id on each result
        for i, result_orm in enumerate(results_orm.results):
            if i < len(results_obj.data):
                results_obj.data[i]._orm_id = result_orm.id
        
        return results_obj
    return None


def delete_result(session: Session, result_id: int) -> bool:
    """Delete a Result from the database."""
    result_orm = session.get(SQLResult, result_id)
    if result_orm:
        session.delete(result_orm)
        return True
    return False


def delete_results(session: Session, results_id: int) -> bool:
    """Delete a Results collection from the database."""
    results_orm = session.get(SQLResults, results_id)
    if results_orm:
        session.delete(results_orm)
        return True
    return False


def list_results(session: Session, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List results in the database with pagination."""
    results = session.query(SQLResult).order_by(SQLResult.created_at.desc()) \
        .limit(limit).offset(offset).all()
    return [{"id": r.id, "agent_id": r.agent_id, "scenario_id": r.scenario_id, 
             "model_id": r.model_id, "iteration": r.iteration, 
             "created_at": r.created_at} for r in results]


def list_results_collections(session: Session, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List results collections in the database with pagination."""
    collections = session.query(SQLResults).order_by(SQLResults.created_at.desc()) \
        .limit(limit).offset(offset).all()
    return [{"id": c.id, "survey_id": c.survey_id, "job_uuid": c.job_uuid,
             "total_results": c.total_results, "completed": c.completed,
             "created_at": c.created_at,
             "result_count": len(c.results)} for c in collections]


def print_sql_schema(engine):
    """Print the SQL schema for the results-related tables."""
    from sqlalchemy.schema import CreateTable
    
    print("\n--- SQL Schema for Results Tables ---")
    for table in [
        SQLResult.__table__,
        SQLResultData.__table__,
        SQLResults.__table__,
        results_result_association
    ]:
        print(f"\n-- Table: {table.name}")
        print(CreateTable(table).compile(engine))
    print("--- End of SQL Schema ---")