"""SQLAlchemy ORM models for Memory and MemoryPlan using SQLAlchemy 2.0 style."""

from sqlalchemy import Integer, String, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Dict, Any, TYPE_CHECKING

# Import the shared Base
from .sql_base import Base

from edsl.surveys.memory import Memory
from edsl.surveys.memory.memory_plan import MemoryPlan
    # Forward declarations for ORM classes used in relationships (SQLAlchemy handles string forward refs)
    # class MemoryPlanMappedObject: pass
    # class MemoryMappedObject: pass
    # class MemoryPlanEntryMappedObject: pass

class MemoryMappedObject(Base):
    """SQLAlchemy ORM model for a Memory object."""
    __tablename__ = "memory"
    edsl_class = None

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Memory.data is a list of strings (prior_questions)
    prior_questions: Mapped[List[str]] = mapped_column(JSON, nullable=False)

    # A Memory can be referenced by multiple MemoryPlanEntry objects
    memory_plan_entries: Mapped[List["MemoryPlanEntryMappedObject"]] = relationship(
        "MemoryPlanEntryMappedObject", back_populates="memory"
    )

    def __repr__(self) -> str:
        num_prior_questions = len(self.prior_questions) if self.prior_questions is not None else 0
        return f"MemoryMappedObject(id={self.id}, num_prior_questions={num_prior_questions})"

    def to_edsl_object(self) -> 'Memory':
        """Convert ORM object to EDSL Memory model instance."""
        from edsl.surveys.memory import Memory
        return Memory(prior_questions=list(self.prior_questions))

    @classmethod
    def from_edsl_object(cls, edsl_memory: 'Memory') -> "MemoryMappedObject":
        """Create ORM object from EDSL Memory model instance."""
        # edsl_memory.data is the list of prior_questions
        return cls(prior_questions=list(edsl_memory.data))

class MemoryPlanMappedObject(Base):
    """SQLAlchemy ORM model for a MemoryPlan object."""
    __tablename__ = "memory_plan"
    edsl_class = None

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    survey_question_names: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    question_texts: Mapped[List[str]] = mapped_column(JSON, nullable=False)

    # Relationship to MemoryPlanEntryMappedObject
    # This represents the Dict[str, Memory] structure of MemoryPlan.data
    entries: Mapped[List["MemoryPlanEntryMappedObject"]] = relationship(
        "MemoryPlanEntryMappedObject",
        back_populates="memory_plan",
        cascade="all, delete-orphan"  # Manages lifecycle of entries with the plan
    )

    def __repr__(self) -> str:
        num_entries = len(self.entries) if self.entries is not None else 0
        return f"MemoryPlanMappedObject(id={self.id}, num_entries={num_entries})"

    def to_edsl_object(self) -> 'MemoryPlan':
        """Convert ORM object to EDSL MemoryPlan model instance."""
        from ..surveys.memory.memory_plan import MemoryPlan
        # EDSL Memory is imported by MemoryMappedObject.to_edsl_object implicitly

        # Reconstruct the data dictionary for MemoryPlan: Dict[str, Memory]
        edsl_data: Dict[str, 'Memory'] = {}
        for entry in self.entries:
            edsl_data[entry.focal_question_name] = entry.memory.to_edsl_object()

        memory_plan_edsl = MemoryPlan(survey=None, data=edsl_data)
        memory_plan_edsl.survey_question_names = list(self.survey_question_names)
        memory_plan_edsl.question_texts = list(self.question_texts)
        return memory_plan_edsl

    @classmethod
    def from_edsl_object(cls, edsl_memory_plan: 'MemoryPlan') -> "MemoryPlanMappedObject":
        """Create ORM object from EDSL MemoryPlan model instance."""
        mapped_plan_orm = cls(
            survey_question_names=list(edsl_memory_plan.survey_question_names),
            question_texts=list(edsl_memory_plan.question_texts)
            # 'entries' list will be populated below, SQLAlchemy handles linking
        )

        new_entries = []
        for focal_question, edsl_memory_object in edsl_memory_plan.data.items():
            mapped_memory_orm = MemoryMappedObject.from_edsl_object(edsl_memory_object)
            
            entry_orm = MemoryPlanEntryMappedObject(
                focal_question_name=focal_question
            )
            entry_orm.memory = mapped_memory_orm  # Link entry to its memory object
            new_entries.append(entry_orm)
        
        mapped_plan_orm.entries = new_entries # Assign entries to the plan

        return mapped_plan_orm

class MemoryPlanEntryMappedObject(Base):
    """Association object linking MemoryPlan, focal question, and Memory."""
    __tablename__ = "memory_plan_entry"
    edsl_class = None

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    memory_plan_id: Mapped[int] = mapped_column(ForeignKey("memory_plan.id"), nullable=False)
    focal_question_name: Mapped[str] = mapped_column(String, nullable=False)
    memory_id: Mapped[int] = mapped_column(ForeignKey("memory.id"), nullable=False)

    memory_plan: Mapped["MemoryPlanMappedObject"] = relationship(
        "MemoryPlanMappedObject", back_populates="entries"
    )
    memory: Mapped["MemoryMappedObject"] = relationship(
        "MemoryMappedObject", back_populates="memory_plan_entries"
    )

    __table_args__ = (UniqueConstraint('memory_plan_id', 'focal_question_name', name='uq_memory_plan_focal_question'),)

    def __repr__(self) -> str:
        return (f"MemoryPlanEntryMappedObject(id={self.id}, "
                f"plan_id={self.memory_plan_id}, "
                f"focal_q='{self.focal_question_name}', "
                f"memory_id={self.memory_id})") 

if __name__ == "__main__":
    from .sql_base import create_test_session # Use the test session setup
    from edsl.surveys.memory import Memory, MemoryPlan
    # ORM classes MemoryMappedObject, MemoryPlanMappedObject are defined above

    # create_test_session() also calls Base.metadata.create_all(engine)
    db_session, _, _ = create_test_session() # We get the engine but won't explicitly use or dispose it here

    # Test 1: MemoryMappedObject
    print("\n--- Testing MemoryMappedObject: Save and Fetch ---")
    example_memory_edsl = Memory(prior_questions=["What is your favorite color?", "What is the capital of France?"])
    print(f"Original EDSL Memory: {example_memory_edsl} with data: {example_memory_edsl.data}")

    # Convert to ORM
    memory_orm = MemoryMappedObject.from_edsl_object(example_memory_edsl)
    
    # Add, commit, refresh
    db_session.add(memory_orm)
    db_session.commit()
    db_session.refresh(memory_orm)
    saved_memory_id = memory_orm.id
    print(f"Saved MemoryMappedObject to DB with ID: {saved_memory_id}")

    # Fetch back
    retrieved_memory_orm = db_session.get(MemoryMappedObject, saved_memory_id)
    assert retrieved_memory_orm is not None, "Failed to retrieve MemoryMappedObject from DB."
    print(f"Retrieved MemoryMappedObject: {retrieved_memory_orm}")

    # Convert back to EDSL
    retrieved_memory_edsl = retrieved_memory_orm.to_edsl_object()
    print(f"Converted back to EDSL Memory: {retrieved_memory_edsl} with data: {retrieved_memory_edsl.data}")

    # Verify
    assert retrieved_memory_edsl.data == example_memory_edsl.data, "Memory data mismatch after DB roundtrip."
    print("Memory object save, fetch, and conversion successful.")

    # Test 2: MemoryPlanMappedObject
    print("\n--- Testing MemoryPlanMappedObject: Save and Fetch ---")
    q_focal_name = "test_focal_question"
    mem_for_plan = Memory(prior_questions=["Is this test plan working?", "What is the next step?"])
    example_plan_edsl = MemoryPlan(
        data={q_focal_name: mem_for_plan},
        survey=None 
    )
    example_plan_edsl.survey_question_names = [q_focal_name, "other_q_manual"]
    example_plan_edsl.question_texts = ["Focal text for manual plan", "Other text for manual plan"]

    print(f"Original EDSL MemoryPlan: {example_plan_edsl}")
    print(f"Original EDSL MemoryPlan survey_question_names: {example_plan_edsl.survey_question_names}")
    print(f"Original EDSL MemoryPlan question_texts: {example_plan_edsl.question_texts}")
    print(f"Original EDSL MemoryPlan data: {example_plan_edsl.data}")

    # Convert to ORM
    plan_orm = MemoryPlanMappedObject.from_edsl_object(example_plan_edsl)
    
    # Add, commit, refresh (cascade should save entries and their new memories)
    db_session.add(plan_orm)
    db_session.commit()
    db_session.refresh(plan_orm) # Refresh the plan itself
    # Refresh entries and their associated memories to ensure they are fully loaded with IDs
    for entry in plan_orm.entries:
        db_session.refresh(entry)
        if entry.memory: 
             db_session.refresh(entry.memory)
    
    saved_plan_id = plan_orm.id
    print(f"Saved MemoryPlanMappedObject to DB with ID: {saved_plan_id} and {len(plan_orm.entries)} entries.")

    # Fetch back
    retrieved_plan_orm = db_session.get(MemoryPlanMappedObject, saved_plan_id)
    assert retrieved_plan_orm is not None, "Failed to retrieve MemoryPlanMappedObject from DB."
    print(f"Retrieved MemoryPlanMappedObject: {retrieved_plan_orm} with {len(retrieved_plan_orm.entries)} entries.")

    # Convert back to EDSL
    retrieved_plan_edsl = retrieved_plan_orm.to_edsl_object()
    print(f"Converted back to EDSL MemoryPlan: {retrieved_plan_edsl}")

    # Verify
    assert retrieved_plan_edsl.survey_question_names == example_plan_edsl.survey_question_names, "MemoryPlan survey_question_names mismatch."
    assert retrieved_plan_edsl.question_texts == example_plan_edsl.question_texts, "MemoryPlan question_texts mismatch."
    assert len(retrieved_plan_edsl.data) == len(example_plan_edsl.data), "MemoryPlan data length mismatch."
    for key, edsl_memory_in_plan_data in example_plan_edsl.data.items():
        assert key in retrieved_plan_edsl.data, f"Key '{key}' not found in retrieved MemoryPlan data."
        assert retrieved_plan_edsl.data[key].data == edsl_memory_in_plan_data.data, f"Data mismatch for memory under key '{key}'."
    print("MemoryPlan object save, fetch, and conversion successful.")

    # Session will be closed when the script ends, and in-memory DB will be gone.
    print("\nExample memory_orm.py __main__ finished.")
