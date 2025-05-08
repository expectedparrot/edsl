"""SQLAlchemy ORM models for the Jobs domain objects.

This module provides SQLAlchemy ORM models for persisting Jobs objects
to a database. It includes models for storing Job configuration, component references,
and execution parameters, along with functions for saving, loading, and managing
these objects in the database.
"""

from __future__ import annotations
import json
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, Type

from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime, Table, Boolean, JSON
from sqlalchemy.orm import relationship, Session, backref

# Import domain models
from .jobs import Jobs
from .data_structures import RunConfig, RunEnvironment, RunParameters
from ..base.exceptions import BaseException
from ..base.db_manager import get_db_manager

# Use Base from the central DB Manager
Base = get_db_manager().base


class JobsOrmException(BaseException):
    """Exception raised for errors in the Jobs ORM operations."""
    pass


# Many-to-many relationship tables
jobs_agents = Table(
    "jobs_agents",
    Base.metadata,
    Column("job_id", Integer, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    Column("agent_id", Integer, primary_key=True),
    Column("agent_data", Text, nullable=False)
)

jobs_models = Table(
    "jobs_models",
    Base.metadata,
    Column("job_id", Integer, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    Column("model_id", Integer, primary_key=True),
    Column("model_data", Text, nullable=False)
)

jobs_scenarios = Table(
    "jobs_scenarios",
    Base.metadata,
    Column("job_id", Integer, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    Column("scenario_id", Integer, primary_key=True),
    Column("scenario_data", Text, nullable=False)
)


class SQLJobParameter(Base):
    """SQLAlchemy ORM model for storing key-value pairs of a Job's parameters."""
    
    __tablename__ = "job_parameters"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    parameter_type = Column(String(50), nullable=False)  # 'environment' or 'execution'
    key = Column(String(255), nullable=False)
    value_type = Column(String(50), nullable=False)  # Type of the value (str, int, bool, etc.)
    value_text = Column(Text, nullable=True)  # For string values or serialized objects
    
    # Relationship to parent Job
    job = relationship("SQLJob", back_populates="parameters")
    
    def __repr__(self) -> str:
        """Return string representation of the JobParameter."""
        return f"<SQLJobParameter(id={self.id}, job_id={self.job_id}, type='{self.parameter_type}', key='{self.key}')>"


class SQLJob(Base):
    """SQLAlchemy ORM model for Jobs."""
    
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    description = Column(String(1024), nullable=True)
    survey_data = Column(Text, nullable=False)  # Serialized survey data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Where clauses as JSON
    where_clauses = Column(Text, nullable=True)
    
    # Relationships
    parameters = relationship("SQLJobParameter", back_populates="job", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        """Return string representation of the Job."""
        return f"<SQLJob(id={self.id}, name='{self.name}')>"
    
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
            except (TypeError, ValueError):
                # For dictionaries that can't be serialized to JSON, fall back to pickle
                try:
                    serialized = pickle.dumps(value).hex()
                    return f'pickle:dict', serialized
                except Exception as e:
                    raise JobsOrmException(f"Could not serialize dictionary: {e}")
        elif isinstance(value, list):
            try:
                return 'json:list', json.dumps(value)
            except (TypeError, ValueError):
                # For lists that can't be serialized to JSON, fall back to pickle
                try:
                    serialized = pickle.dumps(value).hex()
                    return f'pickle:list', serialized
                except Exception as e:
                    raise JobsOrmException(f"Could not serialize list: {e}")
        else:
            # For complex types, use pickle
            try:
                serialized = pickle.dumps(value).hex()
                return f'pickle:{type(value).__name__}', serialized
            except Exception as e:
                raise JobsOrmException(f"Could not serialize value of type {type(value)}: {e}")
    
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
            elif value_type == 'json:list':
                return json.loads(value_text)
            elif value_type.startswith('pickle:'):
                try:
                    return pickle.loads(bytes.fromhex(value_text))
                except Exception as e:
                    raise JobsOrmException(f"Could not deserialize pickled value: {e}")
            else:
                raise JobsOrmException(f"Unknown value type: {value_type}")
        except Exception as e:
            print(f"Error deserializing value of type {value_type}: {e}")
            return None
    
    def to_jobs(self) -> Jobs:
        """Convert this ORM model to a Jobs domain object."""
        from ..surveys import Survey
        from ..agents import Agent, AgentList
        from ..language_models import LanguageModel
        from ..scenarios import Scenario, ScenarioList
        
        # Deserialize the survey
        survey_data = self.deserialize_value('pickle:Survey', self.survey_data)
        
        # Create the base Job object
        job = Jobs(survey=survey_data)
        
        # Set name and description
        job.name = self.name if self.name else None
        job.description = self.description if self.description else None
        
        # Add where clauses if they exist
        if self.where_clauses:
            where_clauses = json.loads(self.where_clauses)
            for clause in where_clauses:
                job.where(clause)
        
        # Process agents
        agents = []
        # Find all agent entries from the jobs_agents table
        session = Session.object_session(self)
        agent_records = session.query(jobs_agents).filter(jobs_agents.c.job_id == self.id).all()
        for record in agent_records:
            agent_data = self.deserialize_value('pickle:Agent', record.agent_data)
            agents.append(agent_data)
        
        if agents:
            job.agents = AgentList(agents)
        
        # Process models
        models = []
        # Find all model entries from the jobs_models table
        model_records = session.query(jobs_models).filter(jobs_models.c.job_id == self.id).all()
        for record in model_records:
            model_data = self.deserialize_value('pickle:LanguageModel', record.model_data)
            models.append(model_data)
        
        if models:
            job.models = models
        
        # Process scenarios
        scenarios = []
        # Find all scenario entries from the jobs_scenarios table
        scenario_records = session.query(jobs_scenarios).filter(jobs_scenarios.c.job_id == self.id).all()
        for record in scenario_records:
            scenario_data = self.deserialize_value('pickle:Scenario', record.scenario_data)
            scenarios.append(scenario_data)
        
        if scenarios:
            job.scenarios = ScenarioList(scenarios)
        
        # Process run configuration parameters
        run_env = RunEnvironment()
        run_params = RunParameters()
        
        # Fill in environment parameters
        env_params = [p for p in self.parameters if p.parameter_type == 'environment']
        for param in env_params:
            if param.value_text.startswith("reference:"):
                # Handle special reference values that can't be directly serialized
                ref_type = param.value_text.split(":", 1)[1]
                if ref_type == "bucket_collection":
                    # Create a new bucket collection or leave as None
                    continue  # We'll let the Jobs object handle this
                elif ref_type == "cache":
                    # Create a new cache or leave as None
                    continue  # We'll let the Jobs object handle this
                elif ref_type == "jobs_runner_status":
                    # Create a new jobs_runner_status or leave as None
                    continue  # We'll let the Jobs object handle this
            else:
                # Normal value
                value = self.deserialize_value(param.value_type, param.value_text)
                if value is not None:  # Skip None values due to deserialization errors
                    setattr(run_env, param.key, value)
        
        # Fill in execution parameters
        exec_params = [p for p in self.parameters if p.parameter_type == 'execution']
        for param in exec_params:
            value = self.deserialize_value(param.value_type, param.value_text)
            if value is not None:  # Skip None values due to deserialization errors
                setattr(run_params, param.key, value)
        
        # Set the run configuration
        job.run_config = RunConfig(environment=run_env, parameters=run_params)
        
        # Store the ORM ID in the Jobs object for future reference
        job._orm_id = self.id
        
        return job
    
    @classmethod
    def from_jobs(cls, job: Jobs, session: Optional[Session] = None) -> SQLJob:
        """Create an ORM model from a Jobs domain object."""
        # Create the base job record
        job_orm = cls(
            name=getattr(job, 'name', None),
            description=getattr(job, 'description', None),
            survey_data=cls.serialize_value(job.survey)[1],
            where_clauses=json.dumps(job._where_clauses) if job._where_clauses else None
        )
        
        # Add to session if provided
        if session:
            session.add(job_orm)
            session.flush()
        
        # Process run configuration
        # Environment parameters
        env_dict = job.run_config.environment.__dict__
        for key, value in env_dict.items():
            if value is not None and not key.startswith('_'):
                try:
                    # Check for non-serializable special cases
                    if key == 'bucket_collection' or key == 'cache' or key == 'jobs_runner_status':
                        # Store a reference marker instead - we'll recreate these dynamically on load
                        value_type, value_text = 'str', f"reference:{key}"
                    else:
                        value_type, value_text = cls.serialize_value(value)
                    
                    param = SQLJobParameter(
                        parameter_type='environment',
                        key=key,
                        value_type=value_type,
                        value_text=value_text
                    )
                    job_orm.parameters.append(param)
                except Exception as e:
                    # Skip parameters that can't be serialized
                    print(f"Warning: Could not serialize {key}: {e}")
        
        # Execution parameters
        exec_dict = job.run_config.parameters.__dict__
        for key, value in exec_dict.items():
            if not key.startswith('_'):
                try:
                    value_type, value_text = cls.serialize_value(value)
                    param = SQLJobParameter(
                        parameter_type='execution',
                        key=key,
                        value_type=value_type,
                        value_text=value_text
                    )
                    job_orm.parameters.append(param)
                except Exception as e:
                    # Skip parameters that can't be serialized
                    print(f"Warning: Could not serialize {key}: {e}")
        
        # We need to flush here to get an ID before adding the many-to-many relationships
        if session:
            session.flush()
        
        # Save agents, models, and scenarios if we have a session
        if session and job_orm.id:
            # Save agents
            if job.agents:
                for i, agent in enumerate(job.agents):
                    agent_data = cls.serialize_value(agent)[1]
                    stmt = jobs_agents.insert().values(
                        job_id=job_orm.id,
                        agent_id=i,
                        agent_data=agent_data
                    )
                    session.execute(stmt)
            
            # Save models
            if job.models:
                for i, model in enumerate(job.models):
                    model_data = cls.serialize_value(model)[1]
                    stmt = jobs_models.insert().values(
                        job_id=job_orm.id,
                        model_id=i,
                        model_data=model_data
                    )
                    session.execute(stmt)
            
            # Save scenarios
            if job.scenarios:
                for i, scenario in enumerate(job.scenarios):
                    scenario_data = cls.serialize_value(scenario)[1]
                    stmt = jobs_scenarios.insert().values(
                        job_id=job_orm.id,
                        scenario_id=i,
                        scenario_data=scenario_data
                    )
                    session.execute(stmt)
        
        return job_orm


def save_job(session: Session, job: Jobs, name: Optional[str] = None, description: Optional[str] = None) -> SQLJob:
    """Save a Jobs object to the database.
    
    Args:
        session: The SQLAlchemy session
        job: The Jobs object to save
        name: Optional name for the job
        description: Optional description for the job
        
    Returns:
        The SQLJob ORM object
    """
    # Check if the job already exists
    if hasattr(job, '_orm_id') and job._orm_id:
        # Try to update the existing job
        update_success = update_job(session, job._orm_id, job, name, description)
        if update_success:
            # Get the updated job
            job_orm = session.get(SQLJob, job._orm_id)
            return job_orm
    
    # Set optional name and description if provided
    if name:
        job.name = name
    if description:
        job.description = description
    
    # Create new job (or recreate if update failed)
    job_orm = SQLJob.from_jobs(job, session)
    session.add(job_orm)
    session.flush()
    
    # Store the ORM ID in the domain object for future reference
    job._orm_id = job_orm.id
    
    return job_orm


def load_job(session: Session, job_id: int) -> Optional[Jobs]:
    """Load a Jobs object from the database by ID.
    
    Args:
        session: The SQLAlchemy session
        job_id: The ID of the job to load
        
    Returns:
        The Jobs object or None if not found
    """
    job_orm = session.get(SQLJob, job_id)
    if job_orm:
        job = job_orm.to_jobs()
        job._orm_id = job_orm.id
        return job
    return None


def update_job(session: Session, job_id: int, job: Jobs, name: Optional[str] = None, description: Optional[str] = None) -> bool:
    """Update an existing job in the database.
    
    Args:
        session: The SQLAlchemy session
        job_id: The ID of the job to update
        job: The Jobs object with updated data
        name: Optional name to update
        description: Optional description to update
        
    Returns:
        True if update was successful, False otherwise
    """
    job_orm = session.get(SQLJob, job_id)
    if not job_orm:
        return False
    
    # Update basic attributes
    if name:
        job_orm.name = name
    if description:
        job_orm.description = description
    
    # Update survey data
    job_orm.survey_data = SQLJob.serialize_value(job.survey)[1]
    
    # Update where clauses
    job_orm.where_clauses = json.dumps(job._where_clauses) if job._where_clauses else None
    
    # Delete existing parameters
    for param in list(job_orm.parameters):
        session.delete(param)
    
    # Delete existing agents, models, and scenarios
    session.execute(jobs_agents.delete().where(jobs_agents.c.job_id == job_id))
    session.execute(jobs_models.delete().where(jobs_models.c.job_id == job_id))
    session.execute(jobs_scenarios.delete().where(jobs_scenarios.c.job_id == job_id))
    
    # Add new parameters from run configuration
    # Environment parameters
    env_dict = job.run_config.environment.__dict__
    for key, value in env_dict.items():
        if value is not None and not key.startswith('_'):
            value_type, value_text = SQLJob.serialize_value(value)
            param = SQLJobParameter(
                job_id=job_id,
                parameter_type='environment',
                key=key,
                value_type=value_type,
                value_text=value_text
            )
            session.add(param)
    
    # Execution parameters
    exec_dict = job.run_config.parameters.__dict__
    for key, value in exec_dict.items():
        if not key.startswith('_'):
            value_type, value_text = SQLJob.serialize_value(value)
            param = SQLJobParameter(
                job_id=job_id,
                parameter_type='execution',
                key=key,
                value_type=value_type,
                value_text=value_text
            )
            session.add(param)
    
    # Add new agents, models, and scenarios
    # Save agents
    if job.agents:
        for i, agent in enumerate(job.agents):
            agent_data = SQLJob.serialize_value(agent)[1]
            stmt = jobs_agents.insert().values(
                job_id=job_id,
                agent_id=i,
                agent_data=agent_data
            )
            session.execute(stmt)
    
    # Save models
    if job.models:
        for i, model in enumerate(job.models):
            model_data = SQLJob.serialize_value(model)[1]
            stmt = jobs_models.insert().values(
                job_id=job_id,
                model_id=i,
                model_data=model_data
            )
            session.execute(stmt)
    
    # Save scenarios
    if job.scenarios:
        for i, scenario in enumerate(job.scenarios):
            scenario_data = SQLJob.serialize_value(scenario)[1]
            stmt = jobs_scenarios.insert().values(
                job_id=job_id,
                scenario_id=i,
                scenario_data=scenario_data
            )
            session.execute(stmt)
    
    return True


def delete_job(session: Session, job_id: int) -> bool:
    """Delete a job from the database.
    
    Args:
        session: The SQLAlchemy session
        job_id: The ID of the job to delete
        
    Returns:
        True if deletion was successful, False otherwise
    """
    job_orm = session.get(SQLJob, job_id)
    if job_orm:
        session.delete(job_orm)
        return True
    return False


def list_jobs(session: Session, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List jobs in the database with pagination.
    
    Args:
        session: The SQLAlchemy session
        limit: Maximum number of jobs to return
        offset: Number of jobs to skip
        
    Returns:
        List of dictionaries containing job metadata
    """
    jobs = session.query(SQLJob).order_by(SQLJob.created_at.desc()) \
        .limit(limit).offset(offset).all()
    return [{"id": j.id, "name": j.name, "description": j.description,
             "created_at": j.created_at, "updated_at": j.updated_at} for j in jobs]


def find_jobs_by_name(session: Session, name: str) -> List[SQLJob]:
    """Find all jobs with a specific name.
    
    Args:
        session: The SQLAlchemy session
        name: The name to search for
        
    Returns:
        List of matching SQLJob objects
    """
    return session.query(SQLJob).filter(
        SQLJob.name == name
    ).all()


def search_jobs(session: Session, search_term: str) -> List[SQLJob]:
    """Search for jobs by name or description.
    
    Args:
        session: The SQLAlchemy session
        search_term: The term to search for in name or description
        
    Returns:
        List of matching SQLJob objects
    """
    return session.query(SQLJob).filter(
        (SQLJob.name.like(f"%{search_term}%")) |
        (SQLJob.description.like(f"%{search_term}%"))
    ).all()


def print_sql_schema(engine):
    """Print the SQL schema for the job-related tables.
    
    Args:
        engine: SQLAlchemy engine
    """
    from sqlalchemy.schema import CreateTable
    
    print("\n--- SQL Schema for Job Tables ---")
    for table in [
        SQLJob.__table__,
        SQLJobParameter.__table__,
        jobs_agents,
        jobs_models,
        jobs_scenarios
    ]:
        print(f"\n-- Table: {table.name}")
        print(CreateTable(table).compile(engine))
    print("--- End of SQL Schema ---")


# Add these models to the db_manager's registry
def register_models():
    """Register Jobs ORM models with the central DBManager."""
    db_manager = get_db_manager()
    db_manager.register_module_models('jobs', {
        'SQLJob': SQLJob,
        'SQLJobParameter': SQLJobParameter,
    })
    return db_manager


# Initialize tables - this will be called when the module is imported
db_manager = register_models()


# Implement the to_db and from_db methods for Jobs
def to_db_impl(job, db_connection):
    """Implement to_db method for Jobs class.
    
    Args:
        job: The Jobs object to store
        db_connection: Database connection object
        
    Returns:
        int: ID of the stored job
    """
    with db_connection.session_scope() as session:
        job_orm = save_job(session, job)
        return job_orm.id


def from_db_impl(cls, db_connection, identifier):
    """Implement from_db method for Jobs class.
    
    Args:
        cls: The Jobs class
        db_connection: Database connection object
        identifier: ID of the job to retrieve
        
    Returns:
        Jobs: The retrieved Jobs object
    """
    with db_connection.session_scope() as session:
        return load_job(session, identifier)


# Attach these functions to the Jobs class
def attach_db_methods():
    """Attach to_db and from_db methods to the Jobs class."""
    from .jobs import Jobs
    
    # Add to_db method to Jobs class
    def to_db(self, db_connection):
        return to_db_impl(self, db_connection)
        
    # Add from_db method to Jobs class
    @classmethod
    def from_db(cls, db_connection, identifier):
        return from_db_impl(cls, db_connection, identifier)
    
    # Attach methods to the Jobs class
    Jobs.to_db = to_db
    Jobs.from_db = from_db
    
    return Jobs


# Initialize the Jobs class with DB methods
Jobs = attach_db_methods()