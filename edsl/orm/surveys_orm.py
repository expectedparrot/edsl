from sqlalchemy import Column, Integer, Text, JSON, DateTime, func, ForeignKey, Table, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any, List, Union
import json

from ..surveys.survey import Survey
from ..surveys.memory.memory_plan import MemoryPlan
# EDSL RuleCollection type hint
from ..surveys.rules.rule_collection import RuleCollection
# EDSL Instruction types
from ..instructions import Instruction, ChangeInstruction
# EDSL Question types - needed for isinstance checks and conversion logic
from ..questions import (
    QuestionFreeText, QuestionMultipleChoice, QuestionNumerical, QuestionList,
    QuestionCheckBox, QuestionDict, QuestionYesNo, QuestionTopK, Question
)

from .sql_base import Base, TimestampMixin
# ORM Question Mapped Object types from questions_orm.py
from .questions_orm import (
    QuestionMappedObject, # Base ORM question class
    QuestionFreeTextMappedObject, QuestionMultipleChoiceMappedObject,
    QuestionNumericalMappedObject, QuestionListMappedObject,
    QuestionCheckBoxMappedObject, QuestionDictMappedObject,
    QuestionYesNoMappedObject, QuestionTopKMappedObject
)
# EDSL Survey specific types
from ..surveys.survey import PseudoIndices
from ..instructions import Instruction, ChangeInstruction
# Import EDSL RuleCollection for type hinting and conversion logic
from ..surveys.rules.rule_collection import RuleCollection
# Import ORM object for RuleCollection
from .rules_orm import RuleCollectionMappedObject
# Import new ORM definitions for Memory and MemoryPlan
from .memory_orm import MemoryMappedObject
from .memory_orm import MemoryPlanMappedObject as OrmMemoryPlan
from .memory_orm import MemoryPlanEntryMappedObject as OrmMemoryPlanEntry

from edsl.questions import (
    QuestionFreeText, QuestionMultipleChoice, QuestionNumerical, QuestionList,
    QuestionCheckBox, QuestionDict, QuestionYesNo, QuestionTopK, Question
)

class QuestionGroupMappedObject(Base):
    __tablename__ = "question_group"
    edsl_class = None

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("survey.id"))
    group_name: Mapped[str] = mapped_column()
    start_index: Mapped[int] = mapped_column()
    end_index: Mapped[int] = mapped_column()

    # Relationship to survey
    survey: Mapped["SurveyMappedObject"] = relationship(back_populates="question_groups")

    def __repr__(self):
        return f"QuestionGroupMappedObject(id={self.id}, group_name='{self.group_name}', range=({self.start_index}, {self.end_index}))"


# ORM classes for Instructions (to replace instruction_data JSON)
class InstructionMappedObject(Base):
    __tablename__ = "survey_instructions"
    edsl_class = None

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("survey.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(index=True) # Name of the instruction
    instruction_text: Mapped[str] = mapped_column(Text)

    # For ChangeInstruction, these will be populated. Nullable for base Instruction.
    variable_name: Mapped[Optional[str]] = mapped_column(nullable=True)
    new_value_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    old_value_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    instruction_type: Mapped[str] = mapped_column(String(50)) # Discriminator: 'base_instruction' or 'change_instruction'

    survey: Mapped["SurveyMappedObject"] = relationship(back_populates="instructions")

    __mapper_args__ = {
        'polymorphic_on': instruction_type
    }

    def to_edsl(self) -> Union[Instruction, ChangeInstruction]:
        # This method should be overridden by subclasses
        raise NotImplementedError


class BaseInstructionMapped(InstructionMappedObject):
    __mapper_args__ = {'polymorphic_identity': 'base_instruction'}
    edsl_class = Instruction

    @classmethod
    def from_edsl(cls, name: str, edsl_instr: 'Instruction') -> 'BaseInstructionMapped':
        return cls(
            name=name,
            instruction_text=edsl_instr.text,
            instruction_type='base_instruction'
        )

    def to_edsl(self) -> 'Instruction':
        return Instruction(text=self.instruction_text)


class ChangeInstructionMapped(InstructionMappedObject):
    __mapper_args__ = {'polymorphic_identity': 'change_instruction'}
    edsl_class = ChangeInstruction

    @classmethod
    def from_edsl(cls, name: str, edsl_instr: 'ChangeInstruction') -> 'ChangeInstructionMapped':
        return cls(
            name=name,
            instruction_text=edsl_instr.text,
            variable_name=edsl_instr.variable_name,
            new_value_json=json.dumps(edsl_instr.new_value),
            old_value_json=json.dumps(edsl_instr.old_value) if hasattr(edsl_instr, 'old_value') and edsl_instr.old_value is not None else None,
            instruction_type='change_instruction'
        )

    def to_edsl(self) -> 'ChangeInstruction':
        new_val = json.loads(self.new_value_json) if self.new_value_json else None
        old_val = json.loads(self.old_value_json) if self.old_value_json else None
        return ChangeInstruction(
            text=self.instruction_text,
            variable_name=self.variable_name,
            new_value=new_val,
            old_value=old_val
        )


# Association table for Survey <-> Question link
class SurveyQuestionAssociation(Base):
    __tablename__ = "survey_question_association"
    edsl_class = None
    
    survey_id: Mapped[int] = mapped_column(ForeignKey("survey.id", ondelete="CASCADE"), primary_key=True)
    # Assuming 'questions' table is defined by questions_orm.py and QuestionMappedObject uses __tablename__ = 'questions'
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id", ondelete="CASCADE"), primary_key=True)
    
    is_to_be_randomized: Mapped[bool] = mapped_column(default=False)
    pseudo_index_value: Mapped[Optional[float]] = mapped_column(nullable=True)
    question_order: Mapped[int] = mapped_column() # To maintain order of questions in the survey

    survey: Mapped["SurveyMappedObject"] = relationship(back_populates="question_associations")
    question: Mapped["QuestionMappedObject"] = relationship(lazy="joined") # Eager load question with association


class SurveyMappedObject(Base, TimestampMixin):
    __tablename__ = "survey"
    edsl_class = Survey

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    seed: Mapped[Optional[int]] = mapped_column(nullable=True)
    # Removed: questions_to_randomize: Mapped[List[str]] = mapped_column(JSON, default=list)
    # Removed: pseudo_indices: Mapped[Dict[str, float]] = mapped_column(JSON, default=dict)
    # Removed: instruction_data: Mapped[Dict[str, Dict]] = mapped_column(JSON, default=dict)

    # Relationships
    memory_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("memory_plan.id", name="fk_survey_memory_plan_id", ondelete="SET NULL"), nullable=True)
    memory_plan: Mapped[Optional["OrmMemoryPlan"]] = relationship(
        OrmMemoryPlan,  # Use the class object directly instead of the string "OrmMemoryPlan"
        foreign_keys=[memory_plan_id],
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,  # Added to clarify ownership for delete-orphan cascade
        lazy="selectin" # Or "joined" if preferred
    )

    question_groups: Mapped[List["QuestionGroupMappedObject"]] = relationship(
        back_populates="survey",
        cascade="all, delete-orphan"
    )

    # Direct relationship to RuleCollectionMappedObject
    rule_collection_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("rule_collections.id", name="fk_survey_rule_collection_id", ondelete="SET NULL"), 
        nullable=True
    )
    rule_collection: Mapped[Optional["RuleCollectionMappedObject"]] = relationship(
        "RuleCollectionMappedObject",
        cascade="all, delete-orphan", # If Survey is deleted, delete associated RuleCollection
        single_parent=True,          # Establishes this as the parent for cascade purposes
        uselist=False,               # One-to-one relationship
        lazy="selectin"              # Or "joined" if preferred
    )

    question_associations: Mapped[List["SurveyQuestionAssociation"]] = relationship(
        back_populates="survey",
        cascade="all, delete-orphan",
        order_by="SurveyQuestionAssociation.question_order",
        lazy="selectin" # Good for loading questions with the survey
    )

    instructions: Mapped[List["InstructionMappedObject"]] = relationship(
        "InstructionMappedObject", # Use the base class name string
        back_populates="survey",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self):
        return f"SurveyMappedObject(id={self.id}, seed={self.seed})"

    @classmethod
    def from_edsl_object(cls, edsl_object: 'Survey') -> 'SurveyMappedObject':
        """Converts an EDSL Survey object into a SurveyMappedObject ORM object."""
        
        survey_mapped_obj = cls(
            seed=edsl_object._seed
            # questions_to_randomize, pseudo_indices, instruction_data are now handled by relationships
        )

        # Handle Instructions
        created_instructions = []
        for name, edsl_instr_obj in edsl_object._instruction_names_to_instructions.items():
            if isinstance(edsl_instr_obj, ChangeInstruction):
                instr_orm = ChangeInstructionMapped.from_edsl(name, edsl_instr_obj)
            elif isinstance(edsl_instr_obj, Instruction): # Must be after ChangeInstruction
                instr_orm = BaseInstructionMapped.from_edsl(name, edsl_instr_obj)
            else:
                # This case should ideally not happen if _instruction_names_to_instructions is well-typed
                print(f"Warning: Skipping unknown instruction type: {type(edsl_instr_obj)} for '{name}'")
                continue
            created_instructions.append(instr_orm)
        survey_mapped_obj.instructions = created_instructions

        # Handle Questions
        created_associations = []
        # Ensure edsl_object.questions gives EDSL Question instances
        # The type hint for edsl_object is 'Survey', which has a 'questions' property.
        edsl_questions_list = edsl_object.questions # This should be List[Question]

        for index, edsl_q_instance in enumerate(edsl_questions_list):
            q_orm = None
            # Map EDSL question instance to its ORM counterpart from questions_orm.py
            if isinstance(edsl_q_instance, QuestionFreeText):
                q_orm = QuestionFreeTextMappedObject.from_edsl_object(edsl_q_instance)
            elif isinstance(edsl_q_instance, QuestionMultipleChoice):
                q_orm = QuestionMultipleChoiceMappedObject.from_edsl_object(edsl_q_instance)
            elif isinstance(edsl_q_instance, QuestionNumerical):
                q_orm = QuestionNumericalMappedObject.from_edsl_object(edsl_q_instance)
            elif isinstance(edsl_q_instance, QuestionList):
                q_orm = QuestionListMappedObject.from_edsl_object(edsl_q_instance)
            elif isinstance(edsl_q_instance, QuestionCheckBox):
                q_orm = QuestionCheckBoxMappedObject.from_edsl_object(edsl_q_instance)
            elif isinstance(edsl_q_instance, QuestionDict):
                q_orm = QuestionDictMappedObject.from_edsl_object(edsl_q_instance)
            elif isinstance(edsl_q_instance, QuestionYesNo):
                q_orm = QuestionYesNoMappedObject.from_edsl_object(edsl_q_instance)
            elif isinstance(edsl_q_instance, QuestionTopK):
                q_orm = QuestionTopKMappedObject.from_edsl_object(edsl_q_instance)
            else:
                raise ValueError(f"Unsupported EDSL question type: {type(edsl_q_instance)} with name '{getattr(edsl_q_instance, 'question_name', 'N/A')}'")

            assoc = SurveyQuestionAssociation(
                question=q_orm, # Link to the ORM question object
                is_to_be_randomized=(edsl_q_instance.question_name in edsl_object.questions_to_randomize),
                pseudo_index_value=edsl_object._pseudo_indices.get(edsl_q_instance.question_name),
                question_order=index
            )
            created_associations.append(assoc)
        survey_mapped_obj.question_associations = created_associations
        
        # Handle MemoryPlan (if exists)
        if edsl_object.memory_plan:
            # Convert EDSL MemoryPlan to OrmMemoryPlan using its from_edsl_object
            # This OrmMemoryPlan will be managed by SQLAlchemy session through cascade
            memory_plan_orm = OrmMemoryPlan.from_edsl_object(edsl_object.memory_plan)
            survey_mapped_obj.memory_plan = memory_plan_orm # Assign the ORM object
        else:
            survey_mapped_obj.memory_plan = None

        # Handle QuestionGroups (if exists) - This part seems okay
        if hasattr(edsl_object, 'question_groups') and edsl_object.question_groups:
            for group_name, (start_index, end_index) in edsl_object.question_groups.items():
                group_orm = QuestionGroupMappedObject(
                    group_name=group_name,
                    start_index=start_index,
                    end_index=end_index
                )
                survey_mapped_obj.question_groups.append(group_orm)
        
        # Handle RuleCollection directly
        if edsl_object.rule_collection:
            if isinstance(edsl_object.rule_collection, RuleCollection):
                orm_rc = RuleCollectionMappedObject.from_edsl_object(edsl_object.rule_collection)
                survey_mapped_obj.rule_collection = orm_rc
            else:
                print(f"Warning: survey.rule_collection is not an EDSL RuleCollection instance. Type: {type(edsl_object.rule_collection)}. Skipping rule collection persistence.")
                survey_mapped_obj.rule_collection = None
        else:
            survey_mapped_obj.rule_collection = None

        return survey_mapped_obj

    def to_edsl_object(self) -> 'Survey':
        """Converts this SurveyMappedObject ORM object back into an EDSL Survey object."""
        from ..surveys.survey import Survey, PseudoIndices
        # Instructions already imported

        # Convert OrmMemoryPlan back to EDSL MemoryPlan
        memory_plan_edsl = self.memory_plan.to_edsl_object() if self.memory_plan else None

        question_groups = {}
        for group in self.question_groups:
            question_groups[group.group_name] = (group.start_index, group.end_index)

        # Reconstruct questions, questions_to_randomize, and pseudo_indices
        edsl_questions_list = []
        questions_to_randomize_list = []
        pseudo_indices_dict = {}

        for assoc in self.question_associations: # Ordered by question_order
            # assoc.question is a QuestionMappedObject (e.g. QuestionFreeTextMappedObject)
            # Its to_edsl_object() method returns the EDSL Question object.
            # SQLAlchemy's polymorphic loading ensures assoc.question is the correct subclass.
            edsl_question = assoc.question.to_edsl_object()
            edsl_questions_list.append(edsl_question)

            if assoc.is_to_be_randomized:
                questions_to_randomize_list.append(edsl_question.question_name)
            
            if assoc.pseudo_index_value is not None:
                pseudo_indices_dict[edsl_question.question_name] = assoc.pseudo_index_value
        
        # Reconstruct RuleCollection
        edsl_rc = None
        if self.rule_collection: # Direct link to RuleCollectionMappedObject
            edsl_rc = self.rule_collection.to_edsl_object()

        survey = Survey(
            questions=edsl_questions_list, # Populate with reconstructed EDSL questions
            memory_plan=memory_plan_edsl, # Assign reconstructed EDSL MemoryPlan
            rule_collection=edsl_rc, # Assign reconstructed EDSL RuleCollection
            question_groups=question_groups,
            questions_to_randomize=questions_to_randomize_list # Populate reconstructed list
        )

        if self.seed is not None:
            survey._seed = self.seed

        survey._pseudo_indices = PseudoIndices(pseudo_indices_dict) # Populate reconstructed pseudo_indices

        # Reconstruct instructions
        reconstructed_instructions = {}
        for instr_orm_obj in self.instructions: # List[InstructionMappedObject]
            # Polymorphic loading ensures instr_orm_obj is BaseInstructionMapped or ChangeInstructionMapped
            edsl_instr = instr_orm_obj.to_edsl() # Calls the correct to_edsl method
            reconstructed_instructions[instr_orm_obj.name] = edsl_instr
        survey._instruction_names_to_instructions = reconstructed_instructions
        
        # survey.rule_collection is already set during Survey initialization above

        # Ensure memory plan has the correct survey question names (if memory plan and survey questions exist)
        # This logic might need re-evaluation if survey_question_names on MemoryPlan is sourced differently
        if survey.memory_plan and edsl_questions_list:
            # If memory_plan.survey_question_names was supposed to be derived from the survey's actual questions
            # this is where it could be updated. However, MemoryPlanMappedObject.from_edsl_object
            # already takes survey_question_names from the EDSL MemoryPlan.
            # The existing logic seems to copy from the ORM memory plan back to the EDSL memory plan if empty.
            if not survey.memory_plan.survey_question_names and self.memory_plan and self.memory_plan.survey_question_names:
                 survey.memory_plan.survey_question_names = list(self.memory_plan.survey_question_names)
            if not survey.memory_plan.question_texts and self.memory_plan and self.memory_plan.question_texts:
                 survey.memory_plan.question_texts = list(self.memory_plan.question_texts)


        return survey

    @classmethod
    def example(cls) -> 'SurveyMappedObject':
        """Creates an example SurveyMappedObject instance for testing"""
        from ..surveys.survey import Survey
        return cls.from_edsl_object(Survey.example())