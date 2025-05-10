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
from sqlalchemy.orm import relationship, Session, backref, Mapped, mapped_column

# Import domain models
from ..jobs import Jobs
from ..surveys import Survey
from ..agents import Agent, AgentList
from ..language_models import LanguageModel
from ..scenarios import Scenario
from ..jobs.data_structures import RunConfig, RunParameters, RunEnvironment # For reconstruction

from ..base.exceptions import BaseException

from .sql_base import Base, TimestampMixin
from .surveys_orm import SurveyMappedObject
from .scenarios_orm import ScenarioListMappedObject
from .agents_orm import AgentListMappedObject
from .language_models_orm import ModelListMappedObject # Added import

class JobsOrmException(BaseException):
    """Exception raised for errors in the Jobs ORM operations."""
    pass


class JobsMappedObject(Base, TimestampMixin):
    """SQLAlchemy ORM model for Jobs, reflecting Jobs.to_dict() structure."""
    
    __tablename__ = "jobs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    survey_id: Mapped[int] = mapped_column(ForeignKey("survey.id"))
    survey: Mapped["SurveyMappedObject"] = relationship(lazy="joined", cascade="save-update, merge")
    
    # Relationships to store serialized lists of agents, models, scenarios
    # agent_links: Mapped[List["JobAgentLink"]] = relationship("JobAgentLink", back_populates="job", cascade="all, delete-orphan") # Removed
    agent_list_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agent_list.id"), nullable=True)
    agent_list: Mapped[Optional["AgentListMappedObject"]] = relationship(cascade="save-update, merge, delete, delete-orphan", single_parent=True)

    scenario_list_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scenario_list.id"), nullable=True)
    scenario_list: Mapped[Optional["ScenarioListMappedObject"]] = relationship(
        cascade="save-update, merge, delete, delete-orphan", 
        single_parent=True
    )
    
    model_list_id: Mapped[Optional[int]] = mapped_column(ForeignKey("model_list.id"), nullable=True)
    model_list: Mapped[Optional["ModelListMappedObject"]] = relationship(cascade="save-update, merge, delete, delete-orphan", single_parent=True)
    
    def __repr__(self) -> str:
        """Return string representation of the Job."""
        return f"<JobsMappedObject(id={self.id}, survey_id={self.survey_id})>"
    
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
    
    @classmethod
    def from_edsl_object(cls, edsl_job: Jobs) -> "JobsMappedObject":
        """Converts an EDSL Jobs object to a JobsMappedObject based on to_dict()."""
        
        survey_orm = SurveyMappedObject.from_edsl_object(edsl_job.survey)

        orm_job = cls(
            survey=survey_orm,
        )

        # Populate agent list link
        if edsl_job.agents and len(edsl_job.agents) > 0:
            # Convert EDSL AgentList to AgentListMappedObject
            # The name for the AgentListMappedObject can be None if not specifically named in this context
            agent_list_orm = AgentListMappedObject.from_edsl_object(edsl_job.agents, name=None)
            orm_job.agent_list = agent_list_orm
        else:
            orm_job.agent_list = None # Ensure it's None if no agents

        # Populate model list link
        if edsl_job.models and len(edsl_job.models) > 0:
            # Convert EDSL ModelList to ModelListMappedObject
            model_list_orm = ModelListMappedObject.from_edsl_object(edsl_job.models, name=None)
            orm_job.model_list = model_list_orm
        else:
            orm_job.model_list = None # Ensure it's None if no models
        
        # Populate scenario list link
        if edsl_job.scenarios and len(edsl_job.scenarios) > 0:
            # Convert EDSL ScenarioList to ScenarioListMappedObject
            # The name for the ScenarioListMappedObject can be None if not specifically named in this context
            scenario_list_orm = ScenarioListMappedObject.from_edsl_object(edsl_job.scenarios, name=None)
            orm_job.scenario_list = scenario_list_orm
        else:
            orm_job.scenario_list = None # Ensure it's None if no scenarios
                
        return orm_job

    def to_edsl_object(self) -> Jobs:
        """Converts this JobsMappedObject back to an EDSL Jobs object."""
        
        if not self.survey:
            raise JobsOrmException("Survey relationship is not loaded or is null for this Job.")
        survey = self.survey.to_edsl_object()

        # Deserialize agents from AgentListMappedObject
        agents_list = None # Default to None, Jobs constructor handles it
        if self.agent_list:
            agents_list = self.agent_list.to_edsl_object()
        # If self.agent_list is None, agents_list remains None, which is fine for Jobs constructor.

        # Deserialize models from ModelListMappedObject
        models_list = None # Default to None, Jobs constructor handles it
        if self.model_list:
            models_list = self.model_list.to_edsl_object()
        # If self.model_list is None, models_list remains None, which is fine for Jobs constructor.

        # Deserialize scenarios from ScenarioListMappedObject
        scenarios_list = None # Default to None, Jobs constructor handles it
        if self.scenario_list:
            scenarios_list = self.scenario_list.to_edsl_object()
        # If self.scenario_list is None, scenarios_list remains None, which is fine for Jobs constructor.

        edsl_job = Jobs(survey=survey, agents=agents_list, models=models_list, scenarios=scenarios_list)
        
        return edsl_job


if __name__ == "__main__":
    from .sql_base import create_test_session
    from ..jobs import Jobs
    # from ..surveys import Survey # Already imported
    # from ..agents import Agent # Already imported
    # from ..language_models import LanguageModel # Already imported
    # from ..scenarios import Scenario # Already imported
    # from ..questions import QuestionFreeText # Needed if constructing simple survey manually

    # 1. Create a test session
    db, _, _ = create_test_session()

    # 2. Create an example EDSL Jobs object
    # Using Jobs.example() for simplicity, assuming it creates a valid job with a survey
    try:
        original_edsl_job = Jobs.example(test_model=True) # test_model=True might use a simpler model
        print(f"Original EDSL Job: {original_edsl_job}")
        if original_edsl_job.survey:
            print(f"  Original survey has {len(original_edsl_job.survey.questions)} questions.")
            print(f"  Original job has {len(original_edsl_job.agents) if original_edsl_job.agents else 0} agents.")
            print(f"  Original job has {len(original_edsl_job.models) if original_edsl_job.models else 0} models.")
            print(f"  Original job has {len(original_edsl_job.scenarios) if original_edsl_job.scenarios else 0} scenarios.")
        else:
            print("  Original job has no survey (this might be an issue for ORM mapping).")
            # If Jobs.example() can return a job without a survey, this test needs a more robust example.
            # For now, proceeding assuming Jobs.example() provides a survey.

    except Exception as e:
        print(f"Error creating Jobs.example(): {e}")
        print("Skipping ORM test due to example creation failure.")
        db.close()
        exit()

    # 3. Convert EDSL Jobs object to ORM object
    # The from_edsl_object method now handles survey conversion internally
    job_orm_to_save = JobsMappedObject.from_edsl_object(original_edsl_job)
    print(f"JobsMappedObject (before save) survey_id: {job_orm_to_save.survey.id if job_orm_to_save.survey else 'None'}, "
          f"agent_list_id: {job_orm_to_save.agent_list.id if job_orm_to_save.agent_list else 'None'}, "
          f"model_list_id: {job_orm_to_save.model_list.id if job_orm_to_save.model_list else 'None'}, "
          f"scenario_list_id: {job_orm_to_save.scenario_list.id if job_orm_to_save.scenario_list else 'None'}")

    # 4. Add to DB, commit, refresh
    try:
        db.add(job_orm_to_save) # This should also add the associated SurveyMappedObject due to cascade
        db.commit()
        db.refresh(job_orm_to_save)
        if job_orm_to_save.survey: # Refresh the survey too if it exists and has an ID
            db.refresh(job_orm_to_save.survey)
        if job_orm_to_save.agent_list:
            db.refresh(job_orm_to_save.agent_list)
        if job_orm_to_save.scenario_list:
            db.refresh(job_orm_to_save.scenario_list)
        if job_orm_to_save.model_list:
            db.refresh(job_orm_to_save.model_list)
        print(f"Saved JobsMappedObject with ID: {job_orm_to_save.id}, Created at: {job_orm_to_save.created_at}")
        if job_orm_to_save.survey:
            print(f"  Associated SurveyMappedObject ID: {job_orm_to_save.survey.id}")
        if job_orm_to_save.agent_list:
            print(f"  Associated AgentListMappedObject ID: {job_orm_to_save.agent_list.id}")
        if job_orm_to_save.scenario_list:
            print(f"  Associated ScenarioListMappedObject ID: {job_orm_to_save.scenario_list.id}")
        if job_orm_to_save.model_list:
            print(f"  Associated ModelListMappedObject ID: {job_orm_to_save.model_list.id}")

    except Exception as e:
        print(f"Error saving JobMappedObject to DB: {e}")
        db.rollback()
        db.close()
        exit()

    # 5. Retrieve the ORM object from the DB
    retrieved_job_orm = db.query(JobsMappedObject).filter(JobsMappedObject.id == job_orm_to_save.id).first()

    if not retrieved_job_orm:
        print("ERROR: Failed to retrieve JobMappedObject from DB!")
    else:
        print(f"Retrieved JobsMappedObject ID: {retrieved_job_orm.id}")
        if retrieved_job_orm.survey:
            print(f"  Retrieved survey (ORM) ID: {retrieved_job_orm.survey.id}, Seed: {retrieved_job_orm.survey.seed}")
            print(f"  Number of questions in retrieved survey (ORM): {len(retrieved_job_orm.survey.question_associations)}")
        if retrieved_job_orm.agent_list:
            print(f"  Retrieved agent_list (ORM) ID: {retrieved_job_orm.agent_list.id}, Num agents: {len(retrieved_job_orm.agent_list.agents)}")
        if retrieved_job_orm.scenario_list:
            print(f"  Retrieved scenario_list (ORM) ID: {retrieved_job_orm.scenario_list.id}, Num scenarios: {len(retrieved_job_orm.scenario_list.scenarios)}")
        if retrieved_job_orm.model_list:
            print(f"  Retrieved model_list (ORM) ID: {retrieved_job_orm.model_list.id}, Num models: {len(retrieved_job_orm.model_list.models)}")

        # 6. Convert back to EDSL Jobs object
        try:
            reconstituted_edsl_job = retrieved_job_orm.to_edsl_object()
            print(f"Reconstituted EDSL Job: {reconstituted_edsl_job.survey.name if hasattr(reconstituted_edsl_job.survey, 'name') else 'Survey (no name attr)'}")
            print(f"  Reconstituted survey has {len(reconstituted_edsl_job.survey.questions)} questions.")
            print(f"  Reconstituted job has {len(reconstituted_edsl_job.agents) if reconstituted_edsl_job.agents else 0} agents.")
            print(f"  Reconstituted job has {len(reconstituted_edsl_job.models) if reconstituted_edsl_job.models else 0} models.")
            print(f"  Reconstituted job has {len(reconstituted_edsl_job.scenarios) if reconstituted_edsl_job.scenarios else 0} scenarios.")

            # Basic comparison (can be made more thorough)
            assert len(original_edsl_job.survey.questions) == len(reconstituted_edsl_job.survey.questions)
            assert len(original_edsl_job.agents or []) == len(reconstituted_edsl_job.agents or [])
            assert len(original_edsl_job.scenarios or []) == len(reconstituted_edsl_job.scenarios or [])
            assert len(original_edsl_job.models or []) == len(reconstituted_edsl_job.models or [])
            print("Basic assertions (question count, agent count, scenario count, model count) passed.")

        except Exception as e:
            raise e
            print(f"Error converting retrieved ORM object back to EDSL Job: {e}")

    db.close()
    
