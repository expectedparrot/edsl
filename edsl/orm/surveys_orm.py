from sqlalchemy import Column, Integer, Text, JSON, DateTime, func, ForeignKey, Table, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any, List, Union
import json

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..surveys.survey import Survey
    from ..surveys.memory.memory_plan import MemoryPlan
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

from edsl.questions import (
    QuestionFreeText, QuestionMultipleChoice, QuestionNumerical, QuestionList,
    QuestionCheckBox, QuestionDict, QuestionYesNo, QuestionTopK, Question
)

class MemoryItem(Base):
    __tablename__ = "memory_items"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    memory_plan_id: Mapped[int] = mapped_column(ForeignKey("memory_plan.id"))
    focal_question_name: Mapped[str] = mapped_column()
    prior_questions: Mapped[List[str]] = mapped_column(JSON)  # Using JSON to store list of question names

    memory_plan: Mapped["MemoryPlanMappedObject"] = relationship(back_populates="memories")

    def __repr__(self):
        return f"MemoryItem(id={self.id}, focal_question_name='{self.focal_question_name}', prior_questions={self.prior_questions})"

    def to_edsl_object(self) -> 'MemoryPlan':
        from ..surveys.memory.memory_plan import MemoryPlan
        from ..surveys.memory.memory import Memory

        memory_plan = MemoryPlan()
        # Ensure survey_question_names and question_texts are lists, even if None from DB
        memory_plan.survey_question_names = list(self.survey_question_names) if self.survey_question_names is not None else []
        memory_plan.question_texts = list(self.question_texts) if self.question_texts is not None else []

        # Add each memory to the memory plan
        memory = Memory(prior_questions=self.prior_questions)
        memory_plan[self.focal_question_name] = memory

        return memory_plan


class MemoryPlanMappedObject(Base, TimestampMixin):
    __tablename__ = "memory_plan"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    survey_id: Mapped[Optional[int]] = mapped_column(ForeignKey("survey.id"), nullable=True)

    # Store question names and texts as JSON
    survey_question_names: Mapped[List[str]] = mapped_column(JSON, default=list)
    question_texts: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Relationships
    survey: Mapped["SurveyMappedObject"] = relationship(back_populates="memory_plan")
    memories: Mapped[List["MemoryItem"]] = relationship(
        "MemoryItem",
        back_populates="memory_plan",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        memory_count = len(self.memories) if self.memories else 0
        return f"MemoryPlanMappedObject(id={self.id}, memory_count={memory_count})"

    @classmethod
    def from_edsl_object(cls, memory_plan: 'MemoryPlan', survey_id: Optional[int] = None) -> 'MemoryPlanMappedObject':
        # Ensure we have proper lists for the JSON columns
        survey_question_names = list(memory_plan.survey_question_names) if memory_plan.survey_question_names else []
        question_texts = list(memory_plan.question_texts) if memory_plan.question_texts else []

        return cls(
            survey_id=survey_id,
            survey_question_names=survey_question_names,
            question_texts=question_texts
        )

    def to_edsl_object(self) -> 'MemoryPlan':
        from ..surveys.memory.memory_plan import MemoryPlan
        from ..surveys.memory.memory import Memory

        memory_plan = MemoryPlan()
        memory_plan.survey_question_names = list(self.survey_question_names) if self.survey_question_names else []
        memory_plan.question_texts = list(self.question_texts) if self.question_texts else []

        # Add each memory to the memory plan
        for memory_item in self.memories:
            memory = Memory(prior_questions=memory_item.prior_questions)
            memory_plan[memory_item.focal_question_name] = memory

        return memory_plan


class QuestionGroupMappedObject(Base):
    __tablename__ = "question_group"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("survey.id"))
    group_name: Mapped[str] = mapped_column()
    start_index: Mapped[int] = mapped_column()
    end_index: Mapped[int] = mapped_column()

    # Relationship to survey
    survey: Mapped["SurveyMappedObject"] = relationship(back_populates="question_groups")

    def __repr__(self):
        return f"QuestionGroupMappedObject(id={self.id}, group_name='{self.group_name}', range=({self.start_index}, {self.end_index}))"


class RuleReferenceMappedObject(Base):
    __tablename__ = "rule_reference"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    rule_collection_id: Mapped[int] = mapped_column()
    survey_id: Mapped[int] = mapped_column(ForeignKey("survey.id", ondelete="CASCADE"))

    # Relationship to survey
    survey: Mapped["SurveyMappedObject"] = relationship(back_populates="rule_reference")

    def __repr__(self):
        return f"RuleReferenceMappedObject(id={self.id}, rule_collection_id={self.rule_collection_id})"


# ORM classes for Instructions (to replace instruction_data JSON)
class InstructionMappedObject(Base):
    __tablename__ = "survey_instructions"
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

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    seed: Mapped[Optional[int]] = mapped_column(nullable=True)
    # Removed: questions_to_randomize: Mapped[List[str]] = mapped_column(JSON, default=list)
    # Removed: pseudo_indices: Mapped[Dict[str, float]] = mapped_column(JSON, default=dict)
    # Removed: instruction_data: Mapped[Dict[str, Dict]] = mapped_column(JSON, default=dict)

    # Relationships
    memory_plan: Mapped[Optional["MemoryPlanMappedObject"]] = relationship(
        uselist=False,
        back_populates="survey",
        cascade="all, delete-orphan"
    )

    question_groups: Mapped[List["QuestionGroupMappedObject"]] = relationship(
        back_populates="survey",
        cascade="all, delete-orphan"
    )

    rule_reference: Mapped[Optional["RuleReferenceMappedObject"]] = relationship(
        uselist=False,
        back_populates="survey",
        cascade="all, delete-orphan"
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
        
        # Handle MemoryPlan (if exists) - This part seems okay, just ensure it gets linked if created
        if edsl_object.memory_plan:
            memory_plan_orm = MemoryPlanMappedObject.from_edsl_object(edsl_object.memory_plan)
            survey_mapped_obj.memory_plan = memory_plan_orm # Link it to the survey

        # Handle QuestionGroups (if exists) - This part seems okay
        if hasattr(edsl_object, 'question_groups') and edsl_object.question_groups:
            for group_name, (start_index, end_index) in edsl_object.question_groups.items():
                group_orm = QuestionGroupMappedObject(
                    group_name=group_name,
                    start_index=start_index,
                    end_index=end_index
                )
                survey_mapped_obj.question_groups.append(group_orm)
        
        # Handle RuleReference (if exists and edsl_object has rule_collection with an ID)
        # This part is stubbed out in the original, will leave as is unless RuleCollection ORM is defined
        # if edsl_object.rule_collection and hasattr(edsl_object.rule_collection, 'id'): # Assuming rule_collection might have an ID
        #     rule_ref_orm = RuleReferenceMappedObject(rule_collection_id=edsl_object.rule_collection.id)
        #     survey_mapped_obj.rule_reference = rule_ref_orm

        return survey_mapped_obj

    def to_edsl_object(self) -> 'Survey':
        """Converts this SurveyMappedObject ORM object back into an EDSL Survey object."""
        from ..surveys.survey import Survey, PseudoIndices
        # Instructions already imported

        memory_plan = self.memory_plan.to_edsl_object() if self.memory_plan else None

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
        
        survey = Survey(
            questions=edsl_questions_list, # Populate with reconstructed EDSL questions
            memory_plan=memory_plan,
            rule_collection=None,  # Rule collection should be loaded separately if implemented
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


if __name__ == "__main__":
    from .sql_base import create_test_session
    from ..surveys.survey import Survey
    # Assuming MemoryPlan might be needed for direct comparison if Survey.example().memory_plan is complex
    # from ..surveys.memory.memory_plan import MemoryPlan 
    # from ..surveys.memory.memory import Memory # If direct Memory object comparison is needed.
    from ..questions import QuestionFreeText # For example test

    # Create a test session
    db, _, _ = create_test_session()

    print("\n--- Testing Survey ORM Write and Read Identity ---")

    # 1. Create an original EDSL Survey instance
    original_edsl_survey = Survey.example()
    print(f"Original EDSL Survey details:")
    print(f"  Seed: {original_edsl_survey._seed}")
    print(f"  Number of questions: {len(original_edsl_survey.questions)}")
    if original_edsl_survey.questions:
        print(f"  First question name: {original_edsl_survey.questions[0].question_name}")
    print(f"  Questions to randomize: {original_edsl_survey.questions_to_randomize}")
    print(f"  Pseudo_indices: {dict(original_edsl_survey._pseudo_indices)}")
    original_instructions_dict_for_print = {
        name: (instr.text if hasattr(instr, 'text') else str(instr))
        for name, instr in original_edsl_survey._instruction_names_to_instructions.items()
    }
    print(f"  Instructions (summary): {original_instructions_dict_for_print}")


    # 2. Convert to ORM object and prepare for saving (including related objects)
    orm_survey_to_save = SurveyMappedObject.from_edsl_object(original_edsl_survey)

    # MemoryPlan, QuestionGroups, RuleReference are handled inside from_edsl_object if they exist on original_edsl_survey
    # No need for explicit handling here anymore unless Survey.example() is too simple.
    # Example: if original_edsl_survey.memory_plan:
    #    memory_plan_orm = MemoryPlanMappedObject.from_edsl_object(original_edsl_survey.memory_plan, survey_id=None) # survey_id linkage is tricky here
    #    orm_survey_to_save.memory_plan = memory_plan_orm # This is now done inside from_edsl_object

    # if hasattr(original_edsl_survey, 'question_groups') and original_edsl_survey.question_groups:
    #     for group_name, (start_index, end_index) in original_edsl_survey.question_groups.items():
    #         group_orm = QuestionGroupMappedObject(
    #             group_name=group_name,
    #             start_index=start_index,
    #             end_index=end_index
    #             # survey_id will be set by relationship
    #         )
    #         orm_survey_to_save.question_groups.append(group_orm) # Also handled inside from_edsl_object


    # Note: RuleCollection / RuleReference is not explicitly handled here for roundtrip testing
    # as Survey.to_edsl_object sets rule_collection=None.
    # If Survey.example() includes rules that should be persisted and restored via SurveyMappedObject's
    # rule_reference, this part might need enhancement based on RuleCollection's ORM structure.

    # 3. Add to DB session, commit, and refresh to get ID and other DB-generated values
    db.add(orm_survey_to_save)
    db.commit()
    db.refresh(orm_survey_to_save) 
    # Also refresh associated objects that get IDs or DB-generated values
    if orm_survey_to_save.memory_plan:
        db.refresh(orm_survey_to_save.memory_plan)
    for qg_orm in orm_survey_to_save.question_groups:
        db.refresh(qg_orm)
    for instr_orm in orm_survey_to_save.instructions:
        db.refresh(instr_orm)
    for assoc_orm in orm_survey_to_save.question_associations:
        db.refresh(assoc_orm)
        if assoc_orm.question: # Question might be eager loaded, but refresh if needed
            db.refresh(assoc_orm.question)


    saved_survey_id = orm_survey_to_save.id
    print(f"Saved Survey ORM object with ID: {saved_survey_id}, Created at: {orm_survey_to_save.created_at}")
    if orm_survey_to_save.memory_plan:
        db.refresh(orm_survey_to_save.memory_plan) # Refresh to get its ID if needed
        print(f"Saved MemoryPlan ORM object with ID: {orm_survey_to_save.memory_plan.id}")
    for qg_orm in orm_survey_to_save.question_groups:
        db.refresh(qg_orm) # Refresh to get its ID
        print(f"Saved QuestionGroup ORM object with ID: {qg_orm.id}, Group Name: {qg_orm.group_name}")


    # 4. Retrieve the ORM object from the DB
    retrieved_orm_survey = db.query(SurveyMappedObject).filter(SurveyMappedObject.id == saved_survey_id).first()
    
    if not retrieved_orm_survey:
        print("ERROR: Failed to retrieve survey from DB!")
        raise Exception("Failed to retrieve survey from DB for testing.")
    else:
        print(f"Retrieved Survey ORM object: {retrieved_orm_survey}")
        if retrieved_orm_survey.memory_plan:
            print(f"Retrieved MemoryPlan ORM object: {retrieved_orm_survey.memory_plan}")
        for qg_orm in retrieved_orm_survey.question_groups:
            print(f"Retrieved QuestionGroup ORM: {qg_orm}")
        print(f"Retrieved {len(retrieved_orm_survey.instructions)} instructions.")
        print(f"Retrieved {len(retrieved_orm_survey.question_associations)} question associations.")


        # 5. Convert back to EDSL Survey object
        retrieved_edsl_survey = retrieved_orm_survey.to_edsl_object()
        print("Converted retrieved ORM object back to EDSL Survey object.")
        print(f"Retrieved EDSL Survey details:")
        print(f"  Seed: {retrieved_edsl_survey._seed}")
        print(f"  Number of questions: {len(retrieved_edsl_survey.questions)}")
        if retrieved_edsl_survey.questions:
            print(f"  First question name: {retrieved_edsl_survey.questions[0].question_name}")
        print(f"  Questions to randomize: {retrieved_edsl_survey.questions_to_randomize}")
        print(f"  Pseudo_indices: {dict(retrieved_edsl_survey._pseudo_indices)}")
        retrieved_instructions_dict_for_print = {
            name: (instr.text if hasattr(instr, 'text') else str(instr))
            for name, instr in retrieved_edsl_survey._instruction_names_to_instructions.items()
        }
        print(f"  Instructions (summary): {retrieved_instructions_dict_for_print}")

        if retrieved_edsl_survey.memory_plan:
            print(f"  Memory Plan survey_question_names: {retrieved_edsl_survey.memory_plan.survey_question_names}")
            print(f"  Memory Plan question_texts: {retrieved_edsl_survey.memory_plan.question_texts}")
        else:
            print("  Memory Plan: None")
        print(f"  Question Groups: {retrieved_edsl_survey.question_groups}")


        # 6. Assert identity (or equivalence for relevant parts)
        assert original_edsl_survey._seed == retrieved_edsl_survey._seed, "Seed mismatch"
        print("Assertion successful: _seed matches.")

        assert original_edsl_survey.questions_to_randomize == retrieved_edsl_survey.questions_to_randomize, "questions_to_randomize mismatch"
        print("Assertion successful: questions_to_randomize matches.")
        
        assert dict(original_edsl_survey._pseudo_indices) == dict(retrieved_edsl_survey._pseudo_indices), "Pseudo_indices mismatch"
        print("Assertion successful: _pseudo_indices match.")

        # Compare instructions (more robustly)
        assert len(original_edsl_survey._instruction_names_to_instructions) == \
               len(retrieved_edsl_survey._instruction_names_to_instructions), "Instruction count mismatch"
        for name, orig_instr in original_edsl_survey._instruction_names_to_instructions.items():
            assert name in retrieved_edsl_survey._instruction_names_to_instructions, f"Instruction '{name}' missing in retrieved survey"
            retr_instr = retrieved_edsl_survey._instruction_names_to_instructions[name]
            assert type(orig_instr) == type(retr_instr), f"Instruction '{name}' type mismatch: {type(orig_instr)} vs {type(retr_instr)}"
            assert orig_instr.to_dict() == retr_instr.to_dict(), f"Instruction '{name}' content mismatch"
        print("Assertion successful: _instruction_names_to_instructions match.")

        # Compare questions (more robustly)
        assert len(original_edsl_survey.questions) == len(retrieved_edsl_survey.questions), \
            f"Question count mismatch. Original: {len(original_edsl_survey.questions)}, Retrieved: {len(retrieved_edsl_survey.questions)}"
        for i, (orig_q, retr_q) in enumerate(zip(original_edsl_survey.questions, retrieved_edsl_survey.questions)):
            # Assuming EDSL questions have a meaningful __eq__ or to_dict() for comparison
            # For now, compare key attributes. A comprehensive to_dict comparison would be best.
            assert orig_q.question_name == retr_q.question_name, f"Question {i} name mismatch"
            assert orig_q.question_text == retr_q.question_text, f"Question {i} text mismatch"
            # Potentially compare .to_dict() if available and reliable on EDSL questions
            # assert orig_q.to_dict() == retr_q.to_dict(), f"Question {i} ('{orig_q.question_name}') content mismatch"
            # Check if question types are the same
            assert type(orig_q) == type(retr_q), f"Question {i} ('{orig_q.question_name}') type mismatch: {type(orig_q)} vs {type(retr_q)}"
            # Example for MultipleChoice specific attribute
            if isinstance(orig_q, QuestionMultipleChoice) and isinstance(retr_q, QuestionMultipleChoice):
                 assert orig_q.question_options == retr_q.question_options, f"Question {i} ('{orig_q.question_name}') options mismatch"

        print("Assertion successful: Survey questions list matches (name, text, type, and options for MC).")

        if original_edsl_survey.memory_plan:
            assert retrieved_edsl_survey.memory_plan is not None, "Memory plan became None after roundtrip"
            omp = original_edsl_survey.memory_plan
            rmp = retrieved_edsl_survey.memory_plan
            assert omp.survey_question_names == rmp.survey_question_names, "MemoryPlan survey_question_names mismatch"
            assert omp.question_texts == rmp.question_texts, "MemoryPlan question_texts mismatch"
            
            # Assuming MemoryPlan is dict-like for its memories or has an items() method
            # If MemoryPlan stores memories in `_memories` dict:
            original_memories = dict(omp.items() if hasattr(omp, 'items') else omp._memories.items())
            retrieved_memories = dict(rmp.items() if hasattr(rmp, 'items') else rmp._memories.items())

            assert len(original_memories) == len(retrieved_memories), \
                f"MemoryPlan memory count mismatch. Original: {len(original_memories)}, Retrieved: {len(retrieved_memories)}"
            for focal_q_name, orig_mem in original_memories.items():
                 assert focal_q_name in retrieved_memories, f"Focal question '{focal_q_name}' missing in retrieved memory plan"
                 ret_mem = retrieved_memories[focal_q_name]
                 assert orig_mem.prior_questions == ret_mem.prior_questions, \
                    f"Memory for '{focal_q_name}' prior_questions mismatch. Original: {orig_mem.prior_questions}, Retrieved: {ret_mem.prior_questions}"
            print("Assertion successful: MemoryPlan content matches.")

        elif retrieved_edsl_survey.memory_plan is not None:
             assert False, "Memory plan appeared after roundtrip, but original was None"
        else:
            print("Assertion successful: MemoryPlan correctly None on both sides.")

        assert original_edsl_survey.question_groups == retrieved_edsl_survey.question_groups, "Question groups mismatch"
        print("Assertion successful: question_groups match.")

        print("\nSUCCESS: Original EDSL survey's ORM-mapped attributes are identical to the retrieved and reconstructed EDSL survey.")
        print("Note: Survey.questions list is now part of this ORM roundtrip test.")
        print("Note: Rule collection is still not part of this specific test (see comments in code).")

    db.close()