from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
from typing import Optional, Dict, Any, List
import json

Base = declarative_base()


class ServiceDefinitionORM(Base):
    """SQLAlchemy model for ServiceDefinition."""

    __tablename__ = "service_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_collection_name = Column(String(255), nullable=False)
    service_name = Column(String(255), nullable=False, unique=False, index=True)
    description = Column(Text, nullable=False)
    service_endpoint = Column(String(500), nullable=True)
    creator_ep_username = Column(String(255), nullable=True, default="test")

    # Relationships
    parameters = relationship(
        "ParameterDefinitionORM",
        back_populates="service_definition",
        cascade="all, delete-orphan",
    )
    cost = relationship(
        "CostDefinitionORM",
        back_populates="service_definition",
        uselist=False,
        cascade="all, delete-orphan",
    )
    service_returns = relationship(
        "ReturnDefinitionORM",
        back_populates="service_definition",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<ServiceDefinitionORM(id={self.id}, service_name='{self.service_name}')>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert SQLAlchemy model to dictionary format compatible with ServiceDefinition."""
        return {
            "service_collection_name": self.service_collection_name,
            "service_name": self.service_name,
            "description": self.description,
            "service_endpoint": self.service_endpoint,
            "creator_ep_username": self.creator_ep_username,
            "parameters": {param.name: param.to_dict() for param in self.parameters},
            "cost": self.cost.to_dict() if self.cost else None,
            "service_returns": {
                ret.name: ret.to_dict() for ret in self.service_returns
            },
        }

    def to_gateway_dict(self) -> Dict[str, Any]:
        """Convert SQLAlchemy model to dictionary format compatible with gateway API."""
        return {
            "service_collection_name": self.service_collection_name,
            "name": self.service_name,  # Gateway expects 'name'
            "description": self.description,
            "service_location_url": self.service_endpoint,  # Gateway expects 'service_location_url'
            "creator_ep_username": self.creator_ep_username,
            "parameters": {param.name: param.to_dict() for param in self.parameters},
            "cost": self.cost.to_dict() if self.cost else None,
            "service_returns": {
                ret.name: ret.to_dict() for ret in self.service_returns
            },
        }


class ParameterDefinitionORM(Base):
    """SQLAlchemy model for ParameterDefinition."""

    __tablename__ = "parameter_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_definition_id = Column(
        Integer, ForeignKey("service_definitions.id"), nullable=False
    )
    name = Column(String(255), nullable=False)  # The parameter name/key
    type = Column(String(100), nullable=False)
    required = Column(Boolean, nullable=False, default=True)
    description = Column(Text, nullable=False)
    default_value = Column(
        JSON, nullable=True
    )  # Using JSON to store any type of default value

    # Relationships
    service_definition = relationship(
        "ServiceDefinitionORM", back_populates="parameters"
    )

    def __repr__(self):
        return f"<ParameterDefinitionORM(id={self.id}, name='{self.name}', type='{self.type}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert SQLAlchemy model to dictionary format compatible with ParameterDefinition."""
        return {
            "type": self.type,
            "required": self.required,
            "description": self.description,
            "default_value": self.default_value,
        }


class CostDefinitionORM(Base):
    """SQLAlchemy model for CostDefinition."""

    __tablename__ = "cost_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_definition_id = Column(
        Integer, ForeignKey("service_definitions.id"), nullable=False
    )
    unit = Column(String(100), nullable=False)
    per_call_cost = Column(Integer, nullable=False)
    variable_pricing_cost_formula = Column(String(500), nullable=True)
    uses_client_ep_key = Column(Boolean, nullable=False, default=False)

    # Relationships
    service_definition = relationship("ServiceDefinitionORM", back_populates="cost")

    def __repr__(self):
        return f"<CostDefinitionORM(id={self.id}, unit='{self.unit}', per_call_cost={self.per_call_cost})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert SQLAlchemy model to dictionary format compatible with CostDefinition."""
        return {
            "unit": self.unit,
            "per_call_cost": self.per_call_cost,
            "variable_pricing_cost_formula": self.variable_pricing_cost_formula,
            "uses_client_ep_key": self.uses_client_ep_key,
        }


class ReturnDefinitionORM(Base):
    """SQLAlchemy model for ReturnDefinition."""

    __tablename__ = "return_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_definition_id = Column(
        Integer, ForeignKey("service_definitions.id"), nullable=False
    )
    name = Column(String(255), nullable=False)  # The return value name/key
    type = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    coopr_url = Column(Boolean, nullable=False, default=False)

    # Relationships
    service_definition = relationship(
        "ServiceDefinitionORM", back_populates="service_returns"
    )

    def __repr__(self):
        return f"<ReturnDefinitionORM(id={self.id}, name='{self.name}', type='{self.type}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert SQLAlchemy model to dictionary format compatible with ReturnDefinition."""
        return {
            "type": self.type,
            "description": self.description,
            "coopr_url": self.coopr_url,
        }


class ServiceDefinitionRepository:
    """Repository class for CRUD operations on ServiceDefinition models."""

    def __init__(self, session):
        self.session = session

    def create_from_service_definition(self, service_def) -> ServiceDefinitionORM:
        """Create a new ServiceDefinitionORM from a ServiceDefinition dataclass."""
        # Import here to avoid circular imports
        from .authoring import (
            ServiceDefinition,
            ParameterDefinition,
            CostDefinition,
            ReturnDefinition,
        )

        if not isinstance(service_def, ServiceDefinition):
            raise ValueError("Expected ServiceDefinition instance")

        # Create the main service definition
        orm_service = ServiceDefinitionORM(
            service_collection_name=service_def.service_collection_name,
            service_name=service_def.service_name,
            description=service_def.description,
            service_endpoint=service_def.service_endpoint,
            creator_ep_username=service_def.creator_ep_username,
        )

        # Add parameters
        for param_name, param_def in service_def.parameters.items():
            if isinstance(param_def, ParameterDefinition):
                orm_param = ParameterDefinitionORM(
                    name=param_name,
                    type=param_def.type,
                    required=param_def.required,
                    description=param_def.description,
                    default_value=param_def.default_value,
                )
                orm_service.parameters.append(orm_param)

        # Add cost definition
        if isinstance(service_def.cost, CostDefinition):
            orm_cost = CostDefinitionORM(
                unit=service_def.cost.unit,
                per_call_cost=service_def.cost.per_call_cost,
                variable_pricing_cost_formula=service_def.cost.variable_pricing_cost_formula,
                uses_client_ep_key=service_def.cost.uses_client_ep_key,
            )
            orm_service.cost = orm_cost

        # Add return definitions
        for return_name, return_def in service_def.service_returns.items():
            if isinstance(return_def, ReturnDefinition):
                orm_return = ReturnDefinitionORM(
                    name=return_name,
                    type=return_def.type,
                    description=return_def.description,
                    coopr_url=return_def.coopr_url,
                )
                orm_service.service_returns.append(orm_return)

        self.session.add(orm_service)
        self.session.commit()
        return orm_service

    def get_by_name(self, name: str) -> Optional[ServiceDefinitionORM]:
        """Get a service definition by name."""
        return (
            self.session.query(ServiceDefinitionORM)
            .filter_by(service_name=name)
            .first()
        )

    def get_by_id(self, service_id: int) -> Optional[ServiceDefinitionORM]:
        """Get a service definition by ID."""
        return self.session.query(ServiceDefinitionORM).filter_by(id=service_id).first()

    def get_all(self) -> List[ServiceDefinitionORM]:
        """Get all service definitions."""
        return self.session.query(ServiceDefinitionORM).all()

    def update(self, service_id: int, service_def) -> Optional[ServiceDefinitionORM]:
        """Update an existing service definition."""
        orm_service = self.get_by_id(service_id)
        if not orm_service:
            return None

        # Update basic fields
        orm_service.service_collection_name = service_def.service_collection_name
        orm_service.service_name = service_def.service_name
        orm_service.description = service_def.description
        orm_service.service_endpoint = service_def.service_endpoint
        orm_service.creator_ep_username = service_def.creator_ep_username

        # Clear existing relationships
        orm_service.parameters.clear()
        if orm_service.cost:
            self.session.delete(orm_service.cost)
        orm_service.service_returns.clear()

        # Re-add parameters, cost, and returns (similar to create_from_service_definition)
        from .authoring import ParameterDefinition, CostDefinition, ReturnDefinition

        for param_name, param_def in service_def.parameters.items():
            if isinstance(param_def, ParameterDefinition):
                orm_param = ParameterDefinitionORM(
                    name=param_name,
                    type=param_def.type,
                    required=param_def.required,
                    description=param_def.description,
                    default_value=param_def.default_value,
                )
                orm_service.parameters.append(orm_param)

        if isinstance(service_def.cost, CostDefinition):
            orm_cost = CostDefinitionORM(
                unit=service_def.cost.unit,
                per_call_cost=service_def.cost.per_call_cost,
                variable_pricing_cost_formula=service_def.cost.variable_pricing_cost_formula,
                uses_client_ep_key=service_def.cost.uses_client_ep_key,
            )
            orm_service.cost = orm_cost

        for return_name, return_def in service_def.service_returns.items():
            if isinstance(return_def, ReturnDefinition):
                orm_return = ReturnDefinitionORM(
                    name=return_name,
                    type=return_def.type,
                    description=return_def.description,
                    coopr_url=return_def.coopr_url,
                )
                orm_service.service_returns.append(orm_return)

        self.session.commit()
        return orm_service

    def delete(self, service_id: int) -> bool:
        """Delete a service definition by ID."""
        orm_service = self.get_by_id(service_id)
        if not orm_service:
            return False

        self.session.delete(orm_service)
        self.session.commit()
        return True

    def to_service_definition(self, orm_service: ServiceDefinitionORM):
        """Convert SQLAlchemy model back to ServiceDefinition dataclass."""
        from .authoring import (
            ServiceDefinition,
            ParameterDefinition,
            CostDefinition,
            ReturnDefinition,
        )

        # Convert parameters
        parameters = {}
        for param in orm_service.parameters:
            parameters[param.name] = ParameterDefinition(
                type=param.type,
                required=param.required,
                description=param.description,
                default_value=param.default_value,
            )

        # Convert cost
        cost = None
        if orm_service.cost:
            cost = CostDefinition(
                unit=orm_service.cost.unit,
                per_call_cost=orm_service.cost.per_call_cost,
                variable_pricing_cost_formula=orm_service.cost.variable_pricing_cost_formula,
                uses_client_ep_key=orm_service.cost.uses_client_ep_key,
            )

        # Convert returns
        service_returns = {}
        for ret in orm_service.service_returns:
            service_returns[ret.name] = ReturnDefinition(
                type=ret.type, description=ret.description, coopr_url=ret.coopr_url
            )

        return ServiceDefinition(
            service_collection_name=orm_service.service_collection_name,
            service_name=orm_service.service_name,
            description=orm_service.description,
            service_endpoint=orm_service.service_endpoint,
            parameters=parameters,
            cost=cost,
            service_returns=service_returns,
            creator_ep_username=orm_service.creator_ep_username,
        )


def create_database_engine(database_url: str = "sqlite:///service_definitions.db"):
    """Create a SQLAlchemy engine and return it along with a session factory."""
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


def get_repository(session) -> ServiceDefinitionRepository:
    """Get a repository instance with the given session."""
    return ServiceDefinitionRepository(session)
