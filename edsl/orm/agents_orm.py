from sqlalchemy import Column, Integer, Text, JSON, DateTime, func, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import Optional, Dict, Any, List
import tempfile
import os

from typing import TYPE_CHECKING
from ..agents.agent import Agent
from ..agents.agent_list import AgentList

from .sql_base import Base, TimestampMixin


class TraitItem(Base):
    edsl_class = None

    __tablename__ = "agent_trait_items"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agent.id"))
    key: Mapped[str] = mapped_column()
    value: Mapped[Any] = mapped_column(JSON) # Using JSON for flexibility in trait values

    agent: Mapped["AgentMappedObject"] = relationship(back_populates="traits")

    def __repr__(self):
        return f"TraitItem(id={self.id}, key='{self.key}', value='{self.value}')"

class CodebookItem(Base):
    edsl_class = None

    __tablename__ = "agent_codebook_items"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agent.id"))
    key: Mapped[str] = mapped_column()
    value: Mapped[str] = mapped_column(Text) # Codebook values are typically descriptions

    agent: Mapped["AgentMappedObject"] = relationship(back_populates="codebook")

    def __repr__(self):
        return f"CodebookItem(id={self.id}, key='{self.key}', value='{self.value}')"

class AgentMappedObject(Base, TimestampMixin):
    edsl_class = Agent

    __tablename__ = "agent"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(nullable=True)
    instruction: Mapped[Optional[str]] = mapped_column(nullable=True)
    
    traits: Mapped[List["TraitItem"]] = relationship("TraitItem", back_populates="agent", cascade="all, delete-orphan")
    codebook: Mapped[List["CodebookItem"]] = relationship("CodebookItem", back_populates="agent", cascade="all, delete-orphan")
    
    traits_presentation_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    dynamic_traits_function_name: Mapped[Optional[str]] = mapped_column(nullable=True)
    dynamic_traits_function_source_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    answer_question_directly_function_name: Mapped[Optional[str]] = mapped_column(nullable=True)
    answer_question_directly_source_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Foreign key and relationship for AgentList
    agent_list_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agent_list.id"), nullable=True)
    agent_list: Mapped[Optional["AgentListMappedObject"]] = relationship(back_populates="agents")

    @classmethod
    def from_edsl_object(cls, edsl_object: 'Agent'):
        data = edsl_object.to_dict(add_edsl_version=False)
        
        trait_items = []
        if 'traits' in data and isinstance(data['traits'], dict):
            for key, value in data['traits'].items():
                trait_items.append(TraitItem(key=key, value=value))
        
        codebook_items = []
        if 'codebook' in data and isinstance(data['codebook'], dict):
            for key, value in data['codebook'].items():
                codebook_items.append(CodebookItem(key=key, value=str(value))) # Ensure value is string for CodebookItem

        # Remove original dicts as they are now handled by relationships
        data.pop('traits', None)
        data.pop('codebook', None)
        
        return cls(
            **data, 
            traits=trait_items, 
            codebook=codebook_items
        )
    
    def to_edsl_object(self) -> 'Agent':
        """Converts the ORM object back to an EDSL Agent object."""
        traits_dict = {trait.key: trait.value for trait in self.traits or []}
        codebook_dict = {item.key: item.value for item in self.codebook or []}
        
        # Note: 'Agent' class must be imported/available in the scope.
        # This is handled by the import at the top of this file for direct use,
        # or should be handled by the calling context (e.g., in __main__ or service layer).
        from ..agents.agent import Agent

        return Agent(
            name=self.name,
            instruction=self.instruction,
            traits=traits_dict,
            codebook=codebook_dict,
            traits_presentation_template=self.traits_presentation_template,
            dynamic_traits_function_name=self.dynamic_traits_function_name,
            dynamic_traits_function_source_code=self.dynamic_traits_function_source_code,
            answer_question_directly_function_name=self.answer_question_directly_function_name,
            answer_question_directly_source_code=self.answer_question_directly_source_code
            # Add any other necessary fields from the Agent EDSL class that are persisted
        )
    
    @classmethod
    def example(cls) -> 'AgentMappedObject':
        return cls.from_edsl_object(Agent.example())

    def __repr__(self) -> str:
        return f"AgentMappedObject(id={self.id}, name='{self.name}')"

class AgentListMappedObject(Base, TimestampMixin):
    edsl_class = AgentList

    __tablename__ = "agent_list"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # Optional name for the list

    # Relationship to AgentMappedObject: An AgentList has many Agents.
    # If an AgentListMappedObject is deleted, its associated AgentMappedObjects are also deleted.
    agents: Mapped[List["AgentMappedObject"]] = relationship(
        "AgentMappedObject", 
        back_populates="agent_list", 
        cascade="all, delete-orphan"
    )

    @classmethod
    def from_edsl_object(cls, edsl_agent_list: 'AgentList', name: Optional[str] = None) -> 'AgentListMappedObject':
        """
        Converts an EDSL AgentList object into an AgentListMappedObject ORM object.
        This method does not commit it to the session; that's the caller's responsibility.
        """
        mapped_agents = []
        if edsl_agent_list.data:
            for agent_edsl in edsl_agent_list.data:
                agent_mapped = AgentMappedObject.from_edsl_object(agent_edsl)
                mapped_agents.append(agent_mapped)
            
        return cls(name=name, agents=mapped_agents)

    def to_edsl_object(self) -> 'AgentList':
        """
        Converts this AgentListMappedObject ORM object back into an EDSL AgentList object.
        """
        agent_list = AgentList()
        if self.agents:
            for agent_mapped in self.agents:
                agent_edsl = agent_mapped.to_edsl_object()
                agent_list.append(agent_edsl)
        
        return agent_list
        

    def __repr__(self) -> str:
        num_agents = len(self.agents) if self.agents else 0
        return f"AgentListMappedObject(id={self.id}, name='{self.name}', num_agents={num_agents})"
    


    


if __name__ == "__main__":

    from .sql_base import create_test_session

    # from edsl import Agent # Now imported at the top
    from ..agents.agent import Agent
    from ..agents.agent_list import AgentList

    new_agent_orm = AgentMappedObject.from_edsl_object(Agent.example())
    db, _, _ = create_test_session()

    db.add(new_agent_orm)
    db.commit()
    db.refresh(new_agent_orm)

    print(f"Created agent: {new_agent_orm}")

    retrieved_agent = db.query(AgentMappedObject).filter(AgentMappedObject.name == "Test Agent").first()
    if retrieved_agent:
        print(f"Retrieved agent: {retrieved_agent}")
        print(f"Created at: {retrieved_agent.created_at}")
        print("Traits:")
        for trait in retrieved_agent.traits:
            print(f"  {trait.key}: {trait.value} (created at: {trait.created_at})")
        print("Codebook:")
        for item in retrieved_agent.codebook:
            print(f"  {item.key}: {item.value} (created at: {item.created_at})")

    print("\\n--- Testing AgentListMappedObject ---")
    # 1. Create an EDSL AgentList
    # example_agent_list_edsl = AgentList.example() # AgentList is imported at the top
    # example_agent_list_edsl.set_instruction("Instruction for all agents in the list.")
    # # Add a named agent to the list for variety
    # named_agent = Agent(name="SpecificAgent", traits={"skill": "programming"}) # Agent is imported at the top
    # example_agent_list_edsl.append(named_agent)
    # print(f"Original EDSL AgentList: {example_agent_list_edsl}")

    # 2. Convert to AgentListMappedObject
    #agent_list_orm = AgentListMappedObject.from_edsl_object(example_agent_list_edsl, name="MyExampleAgentList")


    example_agent_list = AgentList.pull("542ed9c1-abfb-4d14-ab0b-15f6ea4bd7dc")
    agent_list_orm = AgentListMappedObject.from_edsl_object(example_agent_list, name="MyExampleAgentList")
    
    # 3. Add to DB, commit, refresh
    db.add(agent_list_orm)
    db.commit()
    db.refresh(agent_list_orm)
    print(f"Created AgentListMappedObject: {agent_list_orm}")

    print("Number of agents in the list: ", len(agent_list_orm.agents))

    # if agent_list_orm.agents:
    #     for agent_obj in agent_list_orm.agents:
    #         print(f"  Contained agent: {agent_obj} (Created at: {agent_obj.created_at})")
    #         print(f"    Agent's list ID: {agent_obj.agent_list_id}")


    # 4. Retrieve the AgentListMappedObject from DB
    retrieved_agent_list_orm = db.query(AgentListMappedObject).filter(AgentListMappedObject.name == "MyExampleAgentList").first()
    if retrieved_agent_list_orm:
        print(f"Retrieved AgentListMappedObject: {retrieved_agent_list_orm}")
        print(f"  Created at: {retrieved_agent_list_orm.created_at}")
        print(f"  Number of agents: {len(retrieved_agent_list_orm.agents)}")
        # for agent_obj in retrieved_agent_list_orm.agents:
        #     print(f"    Agent in list: {agent_obj.name}, Traits: {[t.key for t in agent_obj.traits]}")

        # 5. Convert back to EDSL AgentList
        reconstituted_agent_list_edsl = retrieved_agent_list_orm.to_edsl_object()
        #print(f"Reconstituted EDSL AgentList: {reconstituted_agent_list_edsl}")
        
        # Verify content (simple check, more thorough checks might compare .to_dict())
        assert len(reconstituted_agent_list_edsl) == len(example_agent_list)
        # Check if instructions were propagated (Agent.to_edsl_object needs to handle instruction)
        if reconstituted_agent_list_edsl and reconstituted_agent_list_edsl.data and reconstituted_agent_list_edsl[0].instruction:
             print(f"  Instruction of first agent in reconstituted list: {reconstituted_agent_list_edsl[0].instruction}")
        
        # Verify equality based on to_dict representation (more robust)
        # Note: AgentList.to_dict() might have ordering issues if not handled,
        # and hash differences for unsaved EDSL objects vs. reconstituted ones.
        # For a strict test, ensure `to_dict` is canonical (e.g., sorted traits).
        # The AgentList.__eq__ method already uses to_dict with sorting.
        if example_agent_list == reconstituted_agent_list_edsl:
            print("Original and reconstituted EDSL AgentLists are equal.")
        else:
            print("Original and reconstituted EDSL AgentLists are NOT equal. Further checks needed.")
            # print("Original dict:", example_agent_list_edsl.to_dict(add_edsl_version=False, sorted=True))
            # print("Reconstituted dict:", reconstituted_agent_list_edsl.to_dict(add_edsl_version=False, sorted=True))


    db.close()
