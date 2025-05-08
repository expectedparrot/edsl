"""SQLAlchemy ORM models for the LanguageModel domain objects.

This module provides SQLAlchemy ORM models for persisting LanguageModel objects
to a database. It includes models for storing model configuration, parameters,
and service information, along with functions for saving, loading, and managing
these objects in the database.
"""

from __future__ import annotations
import json
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, Type

from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime, Table, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, backref

# Create base class for declarative models
Base = declarative_base()

# Import domain models for conversion
from .language_model import LanguageModel
from .model import Model
from ..base.exceptions import BaseException


class LanguageModelOrmException(BaseException):
    """Exception raised for errors in the LanguageModel ORM operations."""
    pass


class SQLModelParameter(Base):
    """SQLAlchemy ORM model for storing key-value pairs of a LanguageModel's parameters."""
    
    __tablename__ = "model_parameters"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("language_models.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(255), nullable=False)
    value_type = Column(String(50), nullable=False)  # Type of the value (str, int, dict, etc.)
    value_text = Column(Text, nullable=True)  # For string values or serialized objects
    
    # Relationship to parent Model
    model = relationship("SQLLanguageModel", back_populates="parameters")
    
    def __repr__(self) -> str:
        """Return string representation of the ModelParameter."""
        return f"<SQLModelParameter(id={self.id}, model_id={self.model_id}, key='{self.key}')>"


class SQLLanguageModel(Base):
    """SQLAlchemy ORM model for LanguageModel."""
    
    __tablename__ = "language_models"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(255), nullable=False)
    inference_service = Column(String(255), nullable=False)
    remote = Column(Boolean, default=False)
    rpm = Column(Float, nullable=True)
    tpm = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    parameters = relationship("SQLModelParameter", back_populates="model", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        """Return string representation of the LanguageModel."""
        return f"<SQLLanguageModel(id={self.id}, model_name='{self.model_name}', service='{self.inference_service}')>"
    
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
        else:
            # For complex types, use pickle
            try:
                serialized = pickle.dumps(value).hex()
                return f'pickle:{type(value).__name__}', serialized
            except Exception as e:
                raise LanguageModelOrmException(f"Could not serialize value of type {type(value)}: {e}")
    
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
            elif value_type.startswith('pickle:'):
                try:
                    return pickle.loads(bytes.fromhex(value_text))
                except Exception as e:
                    raise LanguageModelOrmException(f"Could not deserialize pickled value: {e}")
            else:
                raise LanguageModelOrmException(f"Unknown value type: {value_type}")
        except Exception as e:
            print(f"Error deserializing value of type {value_type}: {e}")
            return None
    
    def to_model(self) -> LanguageModel:
        """Convert this ORM model to a LanguageModel domain object."""
        # Extract parameters
        params = {}
        for param in self.parameters:
            value = self.deserialize_value(param.value_type, param.value_text)
            if value is not None:  # Skip None values due to deserialization errors
                params[param.key] = value
        
        # Prepare the model creation parameters
        model_params = {
            "model": self.model_name, 
            "service_name": self.inference_service
        }
        
        # Add any special parameters like rpm/tpm if set
        if self.rpm is not None:
            model_params["rpm"] = self.rpm
        
        if self.tpm is not None:
            model_params["tpm"] = self.tpm
            
        # Create the model instance using the Model factory
        model = Model(**model_params)
        
        # Set the parameters explicitly to ensure they're all preserved
        model.parameters.update(params)
        
        # Ensure any parameters that should be direct attributes are set
        for key, value in params.items():
            if key not in model.parameters or key in ['max_tokens', 'logprobs', 'top_logprobs']:
                setattr(model, key, value)
        
        # Set remote flag if applicable
        if self.remote:
            model.remote = True
            
        return model
    
    @classmethod
    def from_model(cls, model: LanguageModel, session: Optional[Session] = None) -> SQLLanguageModel:
        """Create an ORM model from a LanguageModel domain object."""
        # Create the base record
        orm_model = cls(
            model_name=model.model,
            inference_service=model._inference_service_,
            remote=getattr(model, 'remote', False)
        )
        
        # Add rate limit parameters if set
        if hasattr(model, '_rpm'):
            orm_model.rpm = model._rpm
            
        if hasattr(model, '_tpm'):
            orm_model.tpm = model._tpm
        
        # Add parameters
        for key, value in model.parameters.items():
            value_type, value_text = cls.serialize_value(value)
            param = SQLModelParameter(
                key=key,
                value_type=value_type,
                value_text=value_text
            )
            orm_model.parameters.append(param)
        
        # Add to session if provided
        if session:
            session.add(orm_model)
            session.flush()
        
        return orm_model


def save_language_model(session: Session, model: LanguageModel) -> SQLLanguageModel:
    """Save a LanguageModel to the database."""
    # Check if the model already exists
    if hasattr(model, '_orm_id') and model._orm_id:
        # Try to update the existing model
        update_success = update_language_model(session, model._orm_id, model)
        if update_success:
            # Get the updated model
            model_orm = session.get(SQLLanguageModel, model._orm_id)
            return model_orm
    
    # Create new model (or recreate if update failed)
    model_orm = SQLLanguageModel.from_model(model)
    session.add(model_orm)
    session.flush()
    
    # Store the ORM ID in the domain object for future reference
    model._orm_id = model_orm.id
    
    return model_orm


def update_language_model(session: Session, model_id: int, model: LanguageModel) -> bool:
    """Update an existing language model in the database."""
    model_orm = session.get(SQLLanguageModel, model_id)
    if not model_orm:
        return False
    
    # Update basic attributes
    model_orm.model_name = model.model
    model_orm.inference_service = model._inference_service_
    model_orm.remote = getattr(model, 'remote', False)
    
    # Update rate limits if set
    if hasattr(model, '_rpm'):
        model_orm.rpm = model._rpm
        
    if hasattr(model, '_tpm'):
        model_orm.tpm = model._tpm
    
    # Delete existing parameters
    for param in list(model_orm.parameters):
        session.delete(param)
    
    # Add regular parameters from parameters dict
    for key, value in model.parameters.items():
        value_type, value_text = SQLLanguageModel.serialize_value(value)
        param = SQLModelParameter(
            model_id=model_id,
            key=key,
            value_type=value_type,
            value_text=value_text
        )
        session.add(param)
    
    # Add special parameters that might be direct attributes but not in parameters dict
    special_params = ['max_tokens', 'logprobs', 'top_logprobs']
    for param_name in special_params:
        if hasattr(model, param_name) and param_name not in model.parameters:
            value = getattr(model, param_name)
            value_type, value_text = SQLLanguageModel.serialize_value(value)
            param = SQLModelParameter(
                model_id=model_id,
                key=param_name,
                value_type=value_type,
                value_text=value_text
            )
            session.add(param)
    
    return True


def load_language_model(session: Session, model_id: int) -> Optional[LanguageModel]:
    """Load a LanguageModel from the database by ID."""
    model_orm = session.get(SQLLanguageModel, model_id)
    if model_orm:
        model = model_orm.to_model()
        model._orm_id = model_orm.id
        return model
    return None


def delete_language_model(session: Session, model_id: int) -> bool:
    """Delete a LanguageModel from the database."""
    model_orm = session.get(SQLLanguageModel, model_id)
    if model_orm:
        session.delete(model_orm)
        return True
    return False


def list_language_models(session: Session, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List language models in the database with pagination."""
    models = session.query(SQLLanguageModel).order_by(SQLLanguageModel.created_at.desc()) \
        .limit(limit).offset(offset).all()
    return [{"id": m.id, "model_name": m.model_name, "service": m.inference_service,
             "created_at": m.created_at} for m in models]


def find_language_models_by_service(session: Session, service_name: str) -> List[SQLLanguageModel]:
    """Find all language models for a specific service."""
    return session.query(SQLLanguageModel).filter(
        SQLLanguageModel.inference_service == service_name
    ).all()


def find_language_models_by_name(session: Session, model_name: str) -> List[SQLLanguageModel]:
    """Find all language models with a specific name."""
    return session.query(SQLLanguageModel).filter(
        SQLLanguageModel.model_name == model_name
    ).all()


def print_sql_schema(engine):
    """Print the SQL schema for the language model-related tables."""
    from sqlalchemy.schema import CreateTable
    
    print("\n--- SQL Schema for Language Model Tables ---")
    for table in [
        SQLLanguageModel.__table__,
        SQLModelParameter.__table__
    ]:
        print(f"\n-- Table: {table.name}")
        print(CreateTable(table).compile(engine))
    print("--- End of SQL Schema ---")