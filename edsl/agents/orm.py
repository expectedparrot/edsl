"""SQLAlchemy ORM models for the Agent, AgentTraits, and AgentList domain objects.

This module provides SQLAlchemy ORM models for persisting Agent, AgentTraits, and AgentList
objects to a database. It includes models for storing the trait structure of
Agents and the collection structure of AgentList, along with functions for
saving, loading, and managing these objects in the database.
"""

from __future__ import annotations
import json
import pickle
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, Type

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Table
# from sqlalchemy.ext.declarative import declarative_base # Remove local Base definition
from sqlalchemy.orm import relationship, Session, backref

# Import the shared Base
from ..base.sql_model_base import Base

# Import domain models for conversion
from .agent import Agent, AgentTraits
from .agent_list import AgentList
from ..base.exceptions import BaseException


class AgentOrmException(BaseException):
    """Exception raised for errors in the Agent ORM operations."""

    pass


# Many-to-many relationship between AgentList and Agent
agent_list_agent_association = Table(
    "agent_list_agent_association",
    Base.metadata,
    Column(
        "agent_list_id",
        Integer,
        ForeignKey("agent_lists.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "agent_id",
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("position", Integer, nullable=False),  # To maintain agent order
)


class SQLAgentTraits(Base):
    """SQLAlchemy ORM model for storing an AgentTraits object."""

    __tablename__ = "agent_traits_objects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships to contain the trait key-value pairs
    trait_entries = relationship(
        "SQLAgentTraitsEntry",
        back_populates="agent_traits",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Return string representation of the AgentTraits object."""
        return f"<SQLAgentTraits(id={self.id}, entries_count={len(self.trait_entries) if self.trait_entries else 0})>"

    def to_agent_traits(self) -> AgentTraits:
        """Convert this ORM model to an AgentTraits domain object."""
        # Extract traits data
        traits_data = {}
        for entry in self.trait_entries:
            value = SQLAgent.deserialize_value(entry.value_type, entry.value_text)
            if value is not None:  # Skip None values due to deserialization errors
                traits_data[entry.key] = value

        # Create and return the AgentTraits object
        traits = AgentTraits(traits_data)
        traits._orm_id = self.id
        return traits

    @classmethod
    def from_agent_traits(
        cls, agent_traits: AgentTraits, session: Optional[Session] = None
    ) -> "SQLAgentTraits":
        """Create an ORM model from an AgentTraits domain object."""
        # Create the base record
        orm_traits = cls()

        # Add to session if provided to get ID
        if session:
            session.add(orm_traits)
            session.flush()

        # Add trait entries
        for key, value in agent_traits.data.items():
            value_type, value_text = SQLAgent.serialize_value(value)
            entry = SQLAgentTraitsEntry(
                key=key,
                value_type=value_type,
                value_text=value_text,
                agent_traits_id=orm_traits.id if session else None,
            )
            orm_traits.trait_entries.append(entry)

        return orm_traits


class SQLAgentTraitsEntry(Base):
    """SQLAlchemy ORM model for storing key-value pairs of an AgentTraits object."""

    __tablename__ = "agent_traits_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_traits_id = Column(
        Integer,
        ForeignKey("agent_traits_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    key = Column(String(255), nullable=False)
    value_type = Column(
        String(50), nullable=False
    )  # Type of the value (str, int, dict, etc.)
    value_text = Column(Text, nullable=True)  # For string values or serialized objects

    # Relationship to parent AgentTraits
    agent_traits = relationship("SQLAgentTraits", back_populates="trait_entries")

    def __repr__(self) -> str:
        """Return string representation of the AgentTraitsEntry."""
        return f"<SQLAgentTraitsEntry(id={self.id}, agent_traits_id={self.agent_traits_id}, key='{self.key}')>"


class SQLAgentTrait(Base):
    """SQLAlchemy ORM model for storing key-value pairs of an Agent's traits."""

    __tablename__ = "agent_traits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    key = Column(String(255), nullable=False)
    value_type = Column(
        String(50), nullable=False
    )  # Type of the value (str, int, dict, etc.)
    value_text = Column(Text, nullable=True)  # For string values or serialized objects

    # Relationship to parent Agent
    agent = relationship("SQLAgent", back_populates="traits")

    def __repr__(self) -> str:
        """Return string representation of the AgentTrait."""
        return (
            f"<SQLAgentTrait(id={self.id}, agent_id={self.agent_id}, key='{self.key}')>"
        )


class SQLAgentCodebook(Base):
    """SQLAlchemy ORM model for storing Agent codebook entries."""

    __tablename__ = "agent_codebooks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    key = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    # Relationship to parent Agent
    agent = relationship("SQLAgent", back_populates="codebook_entries")

    def __repr__(self) -> str:
        """Return string representation of the AgentCodebook entry."""
        return f"<SQLAgentCodebook(id={self.id}, agent_id={self.agent_id}, key='{self.key}')>"


class SQLAgent(Base):
    """SQLAlchemy ORM model for Agent metadata."""

    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    instruction = Column(Text, nullable=True)
    traits_presentation_template = Column(Text, nullable=True)
    has_dynamic_traits_function = Column(
        String(1), nullable=False, default="0"
    )  # "0" or "1"
    dynamic_traits_function_name = Column(String(255), nullable=True)
    dynamic_traits_function_source_code = Column(Text, nullable=True)
    answer_question_directly_function_name = Column(String(255), nullable=True)
    answer_question_directly_source_code = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    traits = relationship(
        "SQLAgentTrait", back_populates="agent", cascade="all, delete-orphan"
    )
    codebook_entries = relationship(
        "SQLAgentCodebook", back_populates="agent", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """Return string representation of the Agent."""
        return f"<SQLAgent(id={self.id}, name={self.name})>"

    @staticmethod
    def serialize_value(value: Any) -> tuple[str, str]:
        """Serialize a value for storage in the database."""
        if value is None:
            return "null", "null"
        elif isinstance(
            value, bool
        ):  # Check for bool before int (bool is a subclass of int)
            return "bool", str(value).lower()
        elif isinstance(value, str):
            return "str", value
        elif isinstance(value, int):
            return "int", str(value)
        elif isinstance(value, float):
            return "float", str(value)
        else:
            # For complex types, use pickle
            try:
                serialized = pickle.dumps(value).hex()
                return f"pickle:{type(value).__name__}", serialized
            except Exception as e:
                raise AgentOrmException(
                    f"Could not serialize value of type {type(value)}: {e}"
                )

    @staticmethod
    def deserialize_value(value_type: str, value_text: str) -> Any:
        """Deserialize a value from storage."""
        try:
            if value_type == "null":
                return None
            elif value_type == "str":
                return value_text
            elif value_type == "int":
                return int(value_text)
            elif value_type == "float":
                return float(value_text)
            elif value_type == "bool":
                return value_text.lower() == "true"
            elif value_type.startswith("pickle:"):
                try:
                    return pickle.loads(bytes.fromhex(value_text))
                except Exception as e:
                    raise AgentOrmException(f"Could not deserialize pickled value: {e}")
            else:
                raise AgentOrmException(f"Unknown value type: {value_type}")
        except Exception as e:
            print(f"Error deserializing value of type {value_type}: {e}")
            return None

    def to_agent(self) -> Agent:
        """Convert this ORM model to an Agent domain object."""
        # Extract traits
        traits = {}
        for trait in self.traits:
            value = self.deserialize_value(trait.value_type, trait.value_text)
            if value is not None:  # Skip None values due to deserialization errors
                traits[trait.key] = value

        # Extract codebook
        codebook = {}
        for entry in self.codebook_entries:
            codebook[entry.key] = entry.description

        # Create Agent with basic attributes
        agent = Agent(
            traits=traits,
            name=self.name,
            instruction=self.instruction,
            traits_presentation_template=self.traits_presentation_template,
            codebook=codebook,
        )

        # Handle dynamic traits function
        if (
            self.has_dynamic_traits_function == "1"
            and self.dynamic_traits_function_source_code
        ):
            from ..utilities import create_restricted_function

            agent.dynamic_traits_function = create_restricted_function(
                self.dynamic_traits_function_name,
                self.dynamic_traits_function_source_code,
            )
            agent.has_dynamic_traits_function = True
            agent.dynamic_traits_function_name = self.dynamic_traits_function_name

        # Handle direct answer function
        if (
            self.answer_question_directly_source_code
            and self.answer_question_directly_function_name
        ):
            from ..utilities import create_restricted_function
            import types

            answer_method = create_restricted_function(
                self.answer_question_directly_function_name,
                self.answer_question_directly_source_code,
            )
            bound_method = types.MethodType(answer_method, agent)
            setattr(agent, "answer_question_directly", bound_method)
            agent.answer_question_directly_function_name = (
                self.answer_question_directly_function_name
            )

        return agent

    @classmethod
    def from_agent(cls, agent: Agent, session: Optional[Session] = None) -> SQLAgent:
        """Create an ORM model from an Agent domain object."""
        # Create the base record
        orm_agent = cls(
            name=agent.name,
            instruction=agent.instruction if hasattr(agent, 'set_instructions') and agent.set_instructions else None,
            traits_presentation_template=agent.traits_presentation_template if hasattr(agent, 'set_traits_presentation_template') and agent.set_traits_presentation_template else None,
            has_dynamic_traits_function=(
                "1" if getattr(agent, "has_dynamic_traits_function", False) else "0"
            ),
            dynamic_traits_function_name=getattr(
                agent, "dynamic_traits_function_name", None
            ),
            answer_question_directly_function_name=getattr(
                agent, "answer_question_directly_function_name", None
            ),
        )

        # Store function source code if available
        if hasattr(agent, "dynamic_traits_function") and agent.dynamic_traits_function:
            import inspect

            try:
                orm_agent.dynamic_traits_function_source_code = inspect.getsource(
                    agent.dynamic_traits_function
                )
            except (TypeError, OSError):
                print(f"Warning: Could not get source code for dynamic traits function")

        if hasattr(agent, "answer_question_directly"):
            import inspect

            try:
                orm_agent.answer_question_directly_source_code = inspect.getsource(
                    agent.answer_question_directly
                )
            except (TypeError, OSError):
                print(
                    f"Warning: Could not get source code for answer_question_directly function"
                )

        # Add traits
        for key, value in agent.traits.items():
            value_type, value_text = cls.serialize_value(value)
            trait = SQLAgentTrait(key=key, value_type=value_type, value_text=value_text)
            orm_agent.traits.append(trait)

        # Add codebook entries
        for key, description in agent.codebook.items():
            entry = SQLAgentCodebook(key=key, description=description)
            orm_agent.codebook_entries.append(entry)

        # Add to session if provided
        if session:
            session.add(orm_agent)
            session.flush()

        return orm_agent


class SQLAgentList(Base):
    """SQLAlchemy ORM model for AgentList."""

    __tablename__ = "agent_lists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    codebook_json = Column(Text, nullable=True)  # Store shared codebook as JSON

    # Relationships
    agents = relationship(
        "SQLAgent",
        secondary=agent_list_agent_association,
        order_by=agent_list_agent_association.c.position,
        backref=backref("agent_lists", lazy="dynamic"),
    )

    def __repr__(self) -> str:
        """Return string representation of the AgentList."""
        return f"<SQLAgentList(id={self.id}, agents_count={len(self.agents) if self.agents else 0})>"

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

    def to_agent_list(self) -> AgentList:
        """Convert this ORM model to an AgentList domain object."""
        # Convert all agents
        agents = [agent.to_agent() for agent in self.agents]

        # Create the AgentList
        agent_list = AgentList(agents, codebook=self.codebook)

        return agent_list

    @classmethod
    def from_agent_list(cls, agent_list: AgentList, session: Session) -> SQLAgentList:
        """Create an ORM model from an AgentList domain object."""
        # Create the base record
        orm_list = cls()

        # Store codebook if shared across agents
        if len(agent_list) > 0:
            # Get the first agent's codebook
            first_codebook = agent_list[0].codebook

            # Check if all agents have the same codebook
            all_same = all(agent.codebook == first_codebook for agent in agent_list)

            # Only include codebook if it's non-empty and consistent across all agents
            if all_same and first_codebook:
                orm_list.codebook = first_codebook

        # Add to session to get ID
        session.add(orm_list)
        session.flush()

        # Add each agent with position
        for i, agent in enumerate(agent_list):
            # Check if agent already exists in database
            agent_orm = None
            if hasattr(agent, "_orm_id") and agent._orm_id:
                agent_orm = session.get(SQLAgent, agent._orm_id)

            # Create new agent ORM if needed
            if not agent_orm:
                agent_orm = SQLAgent.from_agent(agent, session)

            # Add association with position
            stmt = agent_list_agent_association.insert().values(
                agent_list_id=orm_list.id, agent_id=agent_orm.id, position=i
            )
            session.execute(stmt)

        return orm_list


def save_agent(session: Session, agent: Agent) -> SQLAgent:
    """Save an Agent to the database."""
    # Check if the agent already exists
    if hasattr(agent, "_orm_id") and agent._orm_id:
        # Try to update the existing agent
        update_success = update_agent(session, agent._orm_id, agent)
        if update_success:
            # Get the updated agent
            agent_orm = session.get(SQLAgent, agent._orm_id)
            return agent_orm

    # Create new agent (or recreate if update failed)
    agent_orm = SQLAgent.from_agent(agent)
    session.add(agent_orm)
    session.flush()

    # Store the ORM ID in the domain object for future reference
    agent._orm_id = agent_orm.id

    return agent_orm


def update_agent(session: Session, agent_id: int, agent: Agent) -> bool:
    """Update an existing agent in the database."""
    agent_orm = session.get(SQLAgent, agent_id)
    if not agent_orm:
        return False

    # Update basic attributes
    agent_orm.name = agent.name
    agent_orm.instruction = agent.instruction
    agent_orm.traits_presentation_template = getattr(
        agent, "traits_presentation_template", None
    )
    agent_orm.has_dynamic_traits_function = (
        "1" if getattr(agent, "has_dynamic_traits_function", False) else "0"
    )
    agent_orm.dynamic_traits_function_name = getattr(
        agent, "dynamic_traits_function_name", None
    )
    agent_orm.answer_question_directly_function_name = getattr(
        agent, "answer_question_directly_function_name", None
    )

    # Update function source code if available
    if hasattr(agent, "dynamic_traits_function") and agent.dynamic_traits_function:
        import inspect

        try:
            agent_orm.dynamic_traits_function_source_code = inspect.getsource(
                agent.dynamic_traits_function
            )
        except (TypeError, OSError):
            print(f"Warning: Could not get source code for dynamic traits function")

    if hasattr(agent, "answer_question_directly"):
        import inspect

        try:
            agent_orm.answer_question_directly_source_code = inspect.getsource(
                agent.answer_question_directly
            )
        except (TypeError, OSError):
            print(
                f"Warning: Could not get source code for answer_question_directly function"
            )

    # Delete existing traits
    for trait in list(agent_orm.traits):
        session.delete(trait)

    # Add new traits
    for key, value in agent.traits.items():
        value_type, value_text = SQLAgent.serialize_value(value)
        trait = SQLAgentTrait(
            agent_id=agent_id, key=key, value_type=value_type, value_text=value_text
        )
        session.add(trait)

    # Delete existing codebook entries
    for entry in list(agent_orm.codebook_entries):
        session.delete(entry)

    # Add new codebook entries
    for key, description in agent.codebook.items():
        entry = SQLAgentCodebook(agent_id=agent_id, key=key, description=description)
        session.add(entry)

    return True


def save_agent_list(session: Session, agent_list: AgentList) -> SQLAgentList:
    """Save an AgentList to the database."""
    # Check if the agent list already exists
    agent_list_orm = None
    if hasattr(agent_list, "_orm_id") and agent_list._orm_id:
        agent_list_orm = session.get(SQLAgentList, agent_list._orm_id)

    if agent_list_orm:
        # Update existing agent list
        if len(agent_list) > 0:
            # Get the first agent's codebook
            first_codebook = agent_list[0].codebook

            # Check if all agents have the same codebook
            all_same = all(agent.codebook == first_codebook for agent in agent_list)

            # Only update codebook if it's non-empty and consistent across all agents
            if all_same and first_codebook:
                agent_list_orm.codebook = first_codebook
            else:
                agent_list_orm.codebook = None

        # Clear existing associations
        stmt = agent_list_agent_association.delete().where(
            agent_list_agent_association.c.agent_list_id == agent_list_orm.id
        )
        session.execute(stmt)
    else:
        # Create new agent list
        agent_list_orm = SQLAgentList()

        # Set codebook if applicable
        if len(agent_list) > 0:
            # Get the first agent's codebook
            first_codebook = agent_list[0].codebook

            # Check if all agents have the same codebook
            all_same = all(agent.codebook == first_codebook for agent in agent_list)

            # Only include codebook if it's non-empty and consistent across all agents
            if all_same and first_codebook:
                agent_list_orm.codebook = first_codebook

        session.add(agent_list_orm)
        session.flush()

    # We need to save agents before adding associations
    saved_agent_orms = []

    # Add each agent with position
    for i, agent in enumerate(agent_list):
        # Save the agent
        agent_orm = save_agent(session, agent)
        saved_agent_orms.append(agent_orm)

    # Now add all associations
    for i, agent_orm in enumerate(saved_agent_orms):
        # Add association with position
        stmt = agent_list_agent_association.insert().values(
            agent_list_id=agent_list_orm.id, agent_id=agent_orm.id, position=i
        )
        session.execute(stmt)

    # Store the ORM ID in the domain object for future reference
    agent_list._orm_id = agent_list_orm.id

    return agent_list_orm


def load_agent(session: Session, agent_id: int) -> Optional[Agent]:
    """Load an Agent from the database by ID."""
    agent_orm = session.get(SQLAgent, agent_id)
    if agent_orm:
        agent = agent_orm.to_agent()
        agent._orm_id = agent_orm.id
        return agent
    return None


def load_agent_list(session: Session, agent_list_id: int) -> Optional[AgentList]:
    """Load an AgentList from the database by ID."""
    agent_list_orm = session.get(SQLAgentList, agent_list_id)
    if agent_list_orm:
        agent_list = agent_list_orm.to_agent_list()
        agent_list._orm_id = agent_list_orm.id

        # Set the _orm_id on each agent
        for i, agent_orm in enumerate(agent_list_orm.agents):
            if i < len(agent_list):
                agent_list[i]._orm_id = agent_orm.id

        return agent_list
    return None


def delete_agent(session: Session, agent_id: int) -> bool:
    """Delete an Agent from the database."""
    agent_orm = session.get(SQLAgent, agent_id)
    if agent_orm:
        session.delete(agent_orm)
        return True
    return False


def delete_agent_list(session: Session, agent_list_id: int) -> bool:
    """Delete an AgentList from the database."""
    agent_list_orm = session.get(SQLAgentList, agent_list_id)
    if agent_list_orm:
        session.delete(agent_list_orm)
        return True
    return False


def save_agent_traits(session: Session, agent_traits: AgentTraits) -> SQLAgentTraits:
    """Save an AgentTraits object to the database."""
    # Check if the agent traits already exists
    if hasattr(agent_traits, "_orm_id") and agent_traits._orm_id:
        # Try to update the existing agent traits
        update_success = update_agent_traits(
            session, agent_traits._orm_id, agent_traits
        )
        if update_success:
            # Get the updated agent traits
            agent_traits_orm = session.get(SQLAgentTraits, agent_traits._orm_id)
            return agent_traits_orm

    # Create new agent traits (or recreate if update failed)
    agent_traits_orm = SQLAgentTraits.from_agent_traits(agent_traits, session)
    session.add(agent_traits_orm)
    session.flush()

    # Store the ORM ID in the domain object for future reference
    agent_traits._orm_id = agent_traits_orm.id

    return agent_traits_orm


def update_agent_traits(
    session: Session, agent_traits_id: int, agent_traits: AgentTraits
) -> bool:
    """Update an existing agent traits object in the database."""
    agent_traits_orm = session.get(SQLAgentTraits, agent_traits_id)
    if not agent_traits_orm:
        return False

    # Delete existing trait entries
    for entry in list(agent_traits_orm.trait_entries):
        session.delete(entry)

    # Add new trait entries
    for key, value in agent_traits.data.items():
        value_type, value_text = SQLAgent.serialize_value(value)
        entry = SQLAgentTraitsEntry(
            agent_traits_id=agent_traits_id,
            key=key,
            value_type=value_type,
            value_text=value_text,
        )
        session.add(entry)

    return True


def load_agent_traits(session: Session, agent_traits_id: int) -> Optional[AgentTraits]:
    """Load an AgentTraits object from the database by ID."""
    agent_traits_orm = session.get(SQLAgentTraits, agent_traits_id)
    if agent_traits_orm:
        agent_traits = agent_traits_orm.to_agent_traits()
        agent_traits._orm_id = agent_traits_orm.id
        return agent_traits
    return None


def delete_agent_traits(session: Session, agent_traits_id: int) -> bool:
    """Delete an AgentTraits object from the database."""
    agent_traits_orm = session.get(SQLAgentTraits, agent_traits_id)
    if agent_traits_orm:
        session.delete(agent_traits_orm)
        return True
    return False


def list_agent_traits(
    session: Session, limit: int = 100, offset: int = 0
) -> List[Dict[str, Any]]:
    """List agent traits objects in the database with pagination."""
    traits = (
        session.query(SQLAgentTraits)
        .order_by(SQLAgentTraits.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        {"id": t.id, "created_at": t.created_at, "entry_count": len(t.trait_entries)}
        for t in traits
    ]


def list_agents(
    session: Session, limit: int = 100, offset: int = 0
) -> List[Dict[str, Any]]:
    """List agents in the database with pagination."""
    agents = (
        session.query(SQLAgent)
        .order_by(SQLAgent.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [{"id": a.id, "name": a.name, "created_at": a.created_at} for a in agents]


def list_agent_lists(
    session: Session, limit: int = 100, offset: int = 0
) -> List[Dict[str, Any]]:
    """List agent lists in the database with pagination."""
    lists = (
        session.query(SQLAgentList)
        .order_by(SQLAgentList.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        {
            "id": l.id,
            "name": l.name,
            "created_at": l.created_at,
            "agent_count": len(l.agents),
        }
        for l in lists
    ]


def print_sql_schema(engine):
    """Print the SQL schema for the agent-related tables."""
    from sqlalchemy.schema import CreateTable

    print("\n--- SQL Schema for Agent Tables ---")
    for table in [
        SQLAgent.__table__,
        SQLAgentTrait.__table__,
        SQLAgentCodebook.__table__,
        SQLAgentList.__table__,
        SQLAgentTraits.__table__,
        SQLAgentTraitsEntry.__table__,
        agent_list_agent_association,
    ]:
        print(f"\n-- Table: {table.name}")
        print(CreateTable(table).compile(engine))
    print("--- End of SQL Schema ---")
