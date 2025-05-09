"""SQLAlchemy ORM models for the Survey module and related components."""

from __future__ import annotations
import json

from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, JSON, Table
from sqlalchemy.orm import declarative_base, relationship, backref, Session
from sqlalchemy.schema import CreateTable
from typing import Optional, List, Dict, Any, Union, Type

# Import the base ORM models from the questions module
from ..questions.orm import SQLQuestion

from ..base.sql_model_base import Base

# Import EDSL models for conversion
from .survey import Survey
from .memory.memory import Memory
from .memory.memory_plan import MemoryPlan
from ..prompts import Prompt

# Tables for many-to-many relationships
survey_question_association = Table(
    "survey_question_association",
    Base.metadata,
    Column("survey_id", Integer, ForeignKey("surveys.id", ondelete="CASCADE"), primary_key=True),
    Column("question_id", Integer, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, nullable=False)  # To maintain question order
)

class SQLMemory(Base):
    """SQLAlchemy ORM model for Memory."""
    
    __tablename__ = "memories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    focal_question_name = Column(String, nullable=False)
    
    # Foreign key to memory plan
    memory_plan_id = Column(Integer, ForeignKey("memory_plans.id", ondelete="CASCADE"), nullable=False)
    memory_plan = relationship("SQLMemoryPlan", back_populates="memories")
    
    # Relationship to prior question names (stored as JSON)
    prior_questions_json = Column(Text, nullable=False)
    
    def __repr__(self):
        """Return string representation of the Memory."""
        return f"<SQLMemory(id={self.id}, focal_question_name='{self.focal_question_name}', prior_questions={self.prior_questions})>"
    
    @property
    def prior_questions(self) -> List[str]:
        """Get the list of prior question names."""
        return json.loads(self.prior_questions_json)
    
    @prior_questions.setter
    def prior_questions(self, value: List[str]):
        """Set the list of prior question names."""
        self.prior_questions_json = json.dumps(value)
    
    def to_model(self) -> Memory:
        """Convert ORM object to Memory model instance."""
        return Memory(prior_questions=self.prior_questions)
    
    @classmethod
    def from_model(cls, memory: Memory, focal_question_name: str, memory_plan_id: int) -> SQLMemory:
        """Create ORM object from Memory model instance."""
        return cls(
            focal_question_name=focal_question_name,
            prior_questions=list(memory),
            memory_plan_id=memory_plan_id
        )


class SQLMemoryPlan(Base):
    """SQLAlchemy ORM model for MemoryPlan."""
    
    __tablename__ = "memory_plans"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Relationship to the survey
    survey_id = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"), nullable=True)
    survey = relationship("SQLSurvey", back_populates="memory_plan")
    
    # Relationship to memory items
    memories = relationship("SQLMemory", back_populates="memory_plan", cascade="all, delete-orphan")
    
    # Store the question names and texts
    survey_question_names_json = Column(Text, nullable=False)
    survey_question_texts_json = Column(Text, nullable=False)
    
    def __repr__(self):
        """Return string representation of the MemoryPlan."""
        return f"<SQLMemoryPlan(id={self.id}, memories_count={len(self.memories)})>"
    
    @property
    def survey_question_names(self) -> List[str]:
        """Get the list of survey question names."""
        return json.loads(self.survey_question_names_json)
    
    @survey_question_names.setter
    def survey_question_names(self, value: List[str]):
        """Set the list of survey question names."""
        self.survey_question_names_json = json.dumps(value)
    
    @property
    def survey_question_texts(self) -> List[str]:
        """Get the list of survey question texts."""
        return json.loads(self.survey_question_texts_json)
    
    @survey_question_texts.setter
    def survey_question_texts(self, value: List[str]):
        """Set the list of survey question texts."""
        self.survey_question_texts_json = json.dumps(value)
    
    def to_model(self) -> MemoryPlan:
        """Convert ORM object to MemoryPlan model instance."""
        memory_plan = MemoryPlan()
        memory_plan.survey_question_names = self.survey_question_names
        memory_plan.question_texts = self.survey_question_texts
        
        # Add each memory to the memory plan
        for memory_orm in self.memories:
            memory_plan[memory_orm.focal_question_name] = memory_orm.to_model()
        
        return memory_plan
    
    @classmethod
    def from_model(cls, memory_plan: MemoryPlan, survey_id: Optional[int] = None) -> SQLMemoryPlan:
        """Create ORM object from MemoryPlan model instance."""
        memory_plan_orm = cls(
            survey_id=survey_id,
            survey_question_names=memory_plan.survey_question_names,
            survey_question_texts=memory_plan.question_texts
        )
        
        return memory_plan_orm
    
    def add_memories_from_model(self, memory_plan: MemoryPlan):
        """Add memories from a model MemoryPlan to this ORM instance."""
        for focal_question, memory in memory_plan.items():
            memory_orm = SQLMemory.from_model(memory, focal_question, self.id)
            self.memories.append(memory_orm)


class SQLQuestionGroup(Base):
    """SQLAlchemy ORM model for a question group within a survey."""
    
    __tablename__ = "question_groups"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    survey_id = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    group_name = Column(String, nullable=False)
    start_index = Column(Integer, nullable=False)
    end_index = Column(Integer, nullable=False)
    
    # Relationship to survey
    survey = relationship("SQLSurvey", back_populates="question_groups")
    
    def __repr__(self):
        """Return string representation of the QuestionGroup."""
        return f"<SQLQuestionGroup(id={self.id}, group_name='{self.group_name}', range=({self.start_index}, {self.end_index}))>"


class SQLRuleReference(Base):
    """SQLAlchemy ORM model to reference the rule collection."""
    
    __tablename__ = "rule_references"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_collection_id = Column(Integer, nullable=False)
    survey_id = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    
    # Relationship to survey
    survey = relationship("SQLSurvey", back_populates="rule_reference")
    
    def __repr__(self):
        """Return string representation of the RuleReference."""
        return f"<SQLRuleReference(id={self.id}, rule_collection_id={self.rule_collection_id})>"


class SQLSurvey(Base):
    """SQLAlchemy ORM model for Survey."""
    
    __tablename__ = "surveys"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    _seed = Column(Integer, nullable=True)
    questions_to_randomize_json = Column(Text, nullable=False, default="[]")
    
    # Relationships to other components
    questions = relationship(
        "SQLQuestion", 
        secondary=survey_question_association,
        order_by=survey_question_association.c.position,
        backref=backref("surveys", lazy="dynamic")
    )
    
    memory_plan = relationship("SQLMemoryPlan", uselist=False, back_populates="survey", cascade="all, delete-orphan")
    question_groups = relationship("SQLQuestionGroup", back_populates="survey", cascade="all, delete-orphan")
    rule_reference = relationship("SQLRuleReference", uselist=False, back_populates="survey", cascade="all, delete-orphan")
    
    # Pseudo-indices for storing instructions and their positions
    _pseudo_indices_json = Column(Text, nullable=False, default="{}")
    _instruction_names_to_instructions_json = Column(Text, nullable=False, default="{}")
    
    def __repr__(self):
        """Return string representation of the Survey."""
        return f"<SQLSurvey(id={self.id}, questions_count={len(self.questions)})>"
    
    @property
    def questions_to_randomize(self) -> List[str]:
        """Get the list of questions to randomize."""
        return json.loads(self.questions_to_randomize_json)
    
    @questions_to_randomize.setter
    def questions_to_randomize(self, value: List[str]):
        """Set the list of questions to randomize."""
        self.questions_to_randomize_json = json.dumps(value)
    
    @property
    def _pseudo_indices(self) -> Dict[str, float]:
        """Get the pseudo-indices for instructions."""
        return json.loads(self._pseudo_indices_json)
    
    @_pseudo_indices.setter
    def _pseudo_indices(self, value: Dict[str, float]):
        """Set the pseudo-indices for instructions."""
        self._pseudo_indices_json = json.dumps({k: v for k, v in value.items()})
    
    @property
    def _instruction_names_to_instructions(self) -> Dict[str, Dict]:
        """Get the instruction names to instructions mapping."""
        return json.loads(self._instruction_names_to_instructions_json)
    
    @_instruction_names_to_instructions.setter
    def _instruction_names_to_instructions(self, value: Dict[str, Any]):
        """Set the instruction names to instructions mapping.
        
        NOTE: This only stores the serialized instruction dictionaries,
        not the actual Instruction objects.
        """
        # Serialize the instructions to dictionaries
        serialized = {}
        for name, instruction in value.items():
            if hasattr(instruction, 'to_dict'):
                serialized[name] = instruction.to_dict()
            else:
                serialized[name] = instruction
        
        self._instruction_names_to_instructions_json = json.dumps(serialized)
    
    def to_model(self, with_rule_collection: bool = True) -> Survey:
        """Convert ORM object to Survey model instance.
        
        Args:
            with_rule_collection: If True, loads the rule collection from the database
                                 and includes it in the Survey model.
        """
        from .rules.rule_collection import RuleCollection
        from .rules.orm import load_rule_collection
        from ..instructions import Instruction, ChangeInstruction
        
        # Convert SQLQuestion objects to their model counterparts
        questions = []
        for i, q in enumerate(self.questions):
            question_model = q.to_question()
            questions.append(question_model)
        
        # Convert instructions
        instruction_objects = {}
        for name, instr_dict in self._instruction_names_to_instructions.items():
            if instr_dict.get("edsl_class_name") == "Instruction":
                instruction_objects[name] = Instruction.from_dict(instr_dict)
            elif instr_dict.get("edsl_class_name") == "ChangeInstruction":
                instruction_objects[name] = ChangeInstruction.from_dict(instr_dict)
        
        # Combine questions and instructions
        all_items = questions.copy()
        for name, instr in instruction_objects.items():
            all_items.append(instr)
        
        # Sort by pseudo indices
        all_items.sort(key=lambda x: self._pseudo_indices.get(x.name, 0))
        
        # Convert memory plan
        memory_plan = self.memory_plan.to_model() if self.memory_plan else None
        
        # Convert question groups
        question_groups = {}
        for group in self.question_groups:
            question_groups[group.group_name] = (group.start_index, group.end_index)
        
        # Load rule collection if requested
        rule_collection = None
        if with_rule_collection and self.rule_reference:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            
            # Use the same engine as the current session
            session = Session.object_session(self)
            if session:
                rule_collection = load_rule_collection(session, self.rule_reference.rule_collection_id)
        
        # Create the Survey instance
        survey = Survey(
            questions=all_items,
            memory_plan=memory_plan,
            rule_collection=rule_collection,
            question_groups=question_groups,
            questions_to_randomize=self.questions_to_randomize
        )
        
        # Set the seed if it exists
        if self._seed is not None:
            survey._seed = self._seed
        
        return survey
    
    @classmethod
    def from_model(cls, survey: Survey) -> SQLSurvey:
        """Create ORM object from Survey model instance."""
        # Create the SQLSurvey instance
        survey_orm = cls(
            _seed=survey._seed,
            questions_to_randomize=survey.questions_to_randomize,
            _pseudo_indices=survey._pseudo_indices,
            _instruction_names_to_instructions=survey._instruction_names_to_instructions
        )
        
        return survey_orm


def save_survey(session: Session, survey: Survey) -> SQLSurvey:
    """Save a Survey to the database."""
    from .rules.orm import save_rule_collection
    
    # Create SQLSurvey instance
    survey_orm = SQLSurvey.from_model(survey)
    
    # Add to session and flush to get ID
    session.add(survey_orm)
    session.flush()
    
    # Add questions to the survey with positions
    for i, question in enumerate(survey.questions):
        # Get or create SQLQuestion
        question_orm = session.query(SQLQuestion).filter_by(question_name=question.question_name).first()
        if not question_orm:
            # Import the specific SQLQuestion class for this question type
            from ..questions.orm import (
                SQLQuestionFreeText,
                SQLQuestionMultipleChoice,
                SQLQuestionNumerical,
                SQLQuestionList,
                SQLQuestionCheckBox,
                SQLQuestionYesNo,
                SQLQuestionDict,
                SQLQuestionTopK
            )
            
            # Determine the appropriate SQLQuestion subclass
            question_type = question.__class__.__name__
            if question_type == "QuestionFreeText":
                question_orm = SQLQuestionFreeText.from_question(question)
            elif question_type == "QuestionMultipleChoice":
                question_orm = SQLQuestionMultipleChoice.from_question(question)
            elif question_type == "QuestionNumerical":
                question_orm = SQLQuestionNumerical.from_question(question)
            elif question_type == "QuestionList":
                question_orm = SQLQuestionList.from_question(question)
            elif question_type == "QuestionCheckBox":
                question_orm = SQLQuestionCheckBox.from_question(question)
            elif question_type == "QuestionYesNo":
                question_orm = SQLQuestionYesNo.from_question(question)
            elif question_type == "QuestionDict":
                question_orm = SQLQuestionDict.from_question(question)
            elif question_type == "QuestionTopK":
                question_orm = SQLQuestionTopK.from_question(question)
            else:
                # Use a generic base class if specific one not found
                question_orm = SQLQuestion()
                # Set basic attributes
                question_orm.question_name = question.question_name
                question_orm.question_text = question.question_text
                question_orm.question_type_on_table = question_type
            
            session.add(question_orm)
            session.flush()
        
        # Add the association with position
        stmt = survey_question_association.insert().values(
            survey_id=survey_orm.id,
            question_id=question_orm.id,
            position=i
        )
        session.execute(stmt)
    
    # Save memory plan
    if survey.memory_plan:
        memory_plan_orm = SQLMemoryPlan.from_model(survey.memory_plan, survey_orm.id)
        session.add(memory_plan_orm)
        session.flush()
        memory_plan_orm.add_memories_from_model(survey.memory_plan)
        survey_orm.memory_plan = memory_plan_orm
    
    # Save question groups
    for group_name, (start_index, end_index) in survey.question_groups.items():
        group_orm = SQLQuestionGroup(
            survey_id=survey_orm.id,
            group_name=group_name,
            start_index=start_index,
            end_index=end_index
        )
        session.add(group_orm)
    
    # Save rule collection
    if survey.rule_collection:
        rule_collection_orm = save_rule_collection(session, survey.rule_collection, survey_orm.id)
        rule_ref = SQLRuleReference(
            rule_collection_id=rule_collection_orm.id,
            survey_id=survey_orm.id
        )
        session.add(rule_ref)
    
    return survey_orm


def load_survey(session: Session, survey_id: int) -> Optional[Survey]:
    """Load a Survey from the database by ID."""
    survey_orm = session.query(SQLSurvey).get(survey_id)
    if survey_orm:
        return survey_orm.to_model()
    return None


def delete_survey(session: Session, survey_id: int) -> bool:
    """Delete a Survey from the database."""
    survey_orm = session.query(SQLSurvey).get(survey_id)
    if survey_orm:
        session.delete(survey_orm)
        return True
    return False


def print_sql_schema(engine):
    """Print the SQL schema for the survey-related tables."""
    print("\n--- SQL Schema for Survey Tables ---")
    for table in [
        SQLSurvey.__table__,
        SQLMemoryPlan.__table__,
        SQLMemory.__table__,
        SQLQuestionGroup.__table__,
        SQLRuleReference.__table__,
        survey_question_association
    ]:
        print(f"\n-- Table: {table.name}")
        print(CreateTable(table).compile(engine))
    print("--- End of SQL Schema ---")