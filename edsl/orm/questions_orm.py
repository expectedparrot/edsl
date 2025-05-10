from __future__ import annotations
import json

from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, ForeignKey, Float
from sqlalchemy.orm import sessionmaker, relationship, Mapped, mapped_column
from sqlalchemy.schema import CreateTable

# Import the shared Base
from .sql_base import Base

# Import the EDSL Question types for type hinting and conversion
from ..questions import (
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionNumerical,
    QuestionList,
    QuestionCheckBox,
    QuestionDict,
    QuestionYesNo,
    QuestionTopK
)
from ..prompts import Prompt


# Define the base for declarative models --> REMOVED
# Base = declarative_base()

class QuestionOptionMappedObject(Base):
    __tablename__ = 'question_options'
    edsl_class = None

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('question.id', ondelete="CASCADE"), nullable=False)
    option_value: Mapped[str] = mapped_column(Text, nullable=False) # Using Text to accommodate potentially longer option strings

    # Relationship back to the QuestionMappedObject. Each option belongs to one question.
    question: Mapped["QuestionMappedObject"] = relationship(back_populates="options_relation")

    def __repr__(self):
        return f"<QuestionOptionMappedObject(id={self.id}, value='{self.option_value[:20]}...')>"

# Base model for all questions, using Single Table Inheritance
class QuestionMappedObject(Base):
    __tablename__ = 'question'  # Single table for all question types
    edsl_class = None

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_name: Mapped[str] = mapped_column(nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answering_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_presentation: Mapped[str | None] = mapped_column(Text, nullable=True) # Stores JSON string if Prompt, else raw string

    # Discriminator column: stores the type of question
    question_type: Mapped[str] = mapped_column(String(50), index=True)

    # Columns that are specific to some question types but part of the single table
    # Defaults are important here for types that don't use these fields.
    include_comment: Mapped[bool] = mapped_column(default=True, nullable=False)
    use_code: Mapped[bool] = mapped_column(default=False, nullable=False) # Specific to MultipleChoice
    permissive: Mapped[bool] = mapped_column(default=False, nullable=False)
    min_value: Mapped[float | None] = mapped_column(nullable=True) # Specific to Numerical
    max_value: Mapped[float | None] = mapped_column(nullable=True) # Specific to Numerical
    min_list_items: Mapped[int | None] = mapped_column(nullable=True)
    max_list_items: Mapped[int | None] = mapped_column(nullable=True)
    min_selections: Mapped[int | None] = mapped_column(nullable=True) # CheckBox
    max_selections: Mapped[int | None] = mapped_column(nullable=True) # CheckBox

    # JSON-encoded lists for QuestionDict
    answer_keys_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_types_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_descriptions_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'question_base',  # Identity for the base class
        'polymorphic_on': question_type  # Column used for discrimination
    }

    # Relationship to options, relevant for question types like multiple_choice
    # cascade="all, delete-orphan" means options are deleted when the question is deleted.
    options_relation: Mapped[list["QuestionOptionMappedObject"]] = relationship("QuestionOptionMappedObject", back_populates="question", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self):
        return f"<QuestionMappedObject(id={self.id}, name='{self.question_name}', type='{self.question_type}')>"

# Helper function for JSON serialization/deserialization of Prompt objects
def _serialize_prompt_field(prompt_field):
    if prompt_field is not None:
        if hasattr(prompt_field, 'to_dict'):
            return json.dumps(prompt_field.to_dict())
        return str(prompt_field)
    return None

def _deserialize_prompt_field(json_string_field):
    if json_string_field is not None:
        try:
            data_dict = json.loads(json_string_field)
            return Prompt.from_dict(data_dict)
        except (json.JSONDecodeError, TypeError):
            return json_string_field
    return None

# Specific model for FreeText questions, inheriting from QuestionMappedObject
class QuestionFreeTextMappedObject(QuestionMappedObject):
    __mapper_args__ = {
        'polymorphic_identity': 'free_text',
    }
    edsl_class = QuestionFreeText

    @classmethod
    def from_edsl_object(cls, question: QuestionFreeText) -> QuestionFreeTextMappedObject:
        return cls(
            question_name=question.question_name,
            question_text=question.question_text,
            answering_instructions=_serialize_prompt_field(question.answering_instructions),
            question_presentation=_serialize_prompt_field(question.question_presentation)
        )

    def to_edsl_object(self) -> QuestionFreeText:
        return QuestionFreeText(
            question_name=self.question_name,
            question_text=self.question_text,
            answering_instructions=_deserialize_prompt_field(self.answering_instructions),
            question_presentation=_deserialize_prompt_field(self.question_presentation)
        )

class QuestionMultipleChoiceMappedObject(QuestionMappedObject):
    __mapper_args__ = {
        'polymorphic_identity': 'multiple_choice',
    }
    edsl_class = QuestionMultipleChoice

    @classmethod
    def from_edsl_object(cls, question: QuestionMultipleChoice) -> QuestionMultipleChoiceMappedObject:
        db_question_instance = cls(
            question_name=question.question_name,
            question_text=question.question_text,
            answering_instructions=_serialize_prompt_field(question.answering_instructions),
            question_presentation=_serialize_prompt_field(question.question_presentation),
            include_comment=question._include_comment,
            use_code=question.use_code,
            permissive=question.permissive
        )
        current_options = question.question_options
        db_question_instance.options_relation = [
            QuestionOptionMappedObject(option_value=str(opt_val)) for opt_val in current_options
        ]
        return db_question_instance

    def to_edsl_object(self) -> QuestionMultipleChoice:
        options = [opt.option_value for opt in self.options_relation]
        return QuestionMultipleChoice(
            question_name=self.question_name,
            question_text=self.question_text,
            question_options=options,
            include_comment=self.include_comment,
            use_code=self.use_code,
            answering_instructions=_deserialize_prompt_field(self.answering_instructions),
            question_presentation=_deserialize_prompt_field(self.question_presentation),
            permissive=self.permissive
        )

class QuestionNumericalMappedObject(QuestionMappedObject):
    __mapper_args__ = {
        'polymorphic_identity': 'numerical',
    }
    edsl_class = QuestionNumerical

    @classmethod
    def from_edsl_object(cls, question: QuestionNumerical) -> QuestionNumericalMappedObject:
        return cls(
            question_name=question.question_name,
            question_text=question.question_text,
            answering_instructions=_serialize_prompt_field(question.answering_instructions),
            question_presentation=_serialize_prompt_field(question.question_presentation),
            min_value=question.min_value,
            max_value=question.max_value,
            include_comment=question.include_comment,
            permissive=question.permissive
        )

    def to_edsl_object(self) -> QuestionNumerical:
        return QuestionNumerical(
            question_name=self.question_name,
            question_text=self.question_text,
            min_value=self.min_value,
            max_value=self.max_value,
            answering_instructions=_deserialize_prompt_field(self.answering_instructions),
            question_presentation=_deserialize_prompt_field(self.question_presentation),
            include_comment=self.include_comment,
            permissive=self.permissive
        )

class QuestionListMappedObject(QuestionMappedObject):
    __mapper_args__ = {
        'polymorphic_identity': 'list',
    }
    edsl_class = QuestionList

    @classmethod
    def from_edsl_object(cls, question: QuestionList) -> QuestionListMappedObject:
        return cls(
            question_name=question.question_name,
            question_text=question.question_text,
            answering_instructions=_serialize_prompt_field(question.answering_instructions),
            question_presentation=_serialize_prompt_field(question.question_presentation),
            min_list_items=question.min_list_items,
            max_list_items=question.max_list_items,
            include_comment=question.include_comment,
            permissive=question.permissive
        )

    def to_edsl_object(self) -> QuestionList:
        return QuestionList(
            question_name=self.question_name,
            question_text=self.question_text,
            min_list_items=self.min_list_items,
            max_list_items=self.max_list_items,
            answering_instructions=_deserialize_prompt_field(self.answering_instructions),
            question_presentation=_deserialize_prompt_field(self.question_presentation),
            include_comment=self.include_comment,
            permissive=self.permissive
        )

class QuestionCheckBoxMappedObject(QuestionMappedObject):
    __mapper_args__ = {
        'polymorphic_identity': 'checkbox',
    }
    edsl_class = QuestionCheckBox

    @classmethod
    def from_edsl_object(cls, question: QuestionCheckBox) -> QuestionCheckBoxMappedObject:
        db_question_instance = cls(
            question_name=question.question_name,
            question_text=question.question_text,
            answering_instructions=_serialize_prompt_field(question.answering_instructions),
            question_presentation=_serialize_prompt_field(question.question_presentation),
            min_selections=question.min_selections,
            max_selections=question.max_selections,
            include_comment=question._include_comment,
            use_code=question._use_code,
            permissive=question.permissive
        )
        current_options = question.question_options
        db_question_instance.options_relation = [
            QuestionOptionMappedObject(option_value=str(opt_val)) for opt_val in current_options
        ]
        return db_question_instance

    def to_edsl_object(self) -> QuestionCheckBox:
        options = [opt.option_value for opt in self.options_relation]
        return QuestionCheckBox(
            question_name=self.question_name,
            question_text=self.question_text,
            question_options=options,
            min_selections=self.min_selections,
            max_selections=self.max_selections,
            answering_instructions=_deserialize_prompt_field(self.answering_instructions),
            question_presentation=_deserialize_prompt_field(self.question_presentation),
            include_comment=self.include_comment,
            use_code=self.use_code,
            permissive=self.permissive
        )

class QuestionDictMappedObject(QuestionMappedObject):
    __mapper_args__ = {
        'polymorphic_identity': 'dict',
    }
    edsl_class = QuestionDict

    @classmethod
    def from_edsl_object(cls, question: QuestionDict) -> QuestionDictMappedObject:
        return cls(
            question_name=question.question_name,
            question_text=question.question_text,
            answering_instructions=_serialize_prompt_field(question.answering_instructions),
            question_presentation=_serialize_prompt_field(question.question_presentation),
            answer_keys_json=json.dumps(question.answer_keys or []),
            value_types_json=json.dumps(question.value_types or []),
            value_descriptions_json=json.dumps(question.value_descriptions or []),
            include_comment=question.include_comment,
            permissive=question.permissive
        )

    def to_edsl_object(self) -> QuestionDict:
        return QuestionDict(
            question_name=self.question_name,
            question_text=self.question_text,
            answer_keys=json.loads(self.answer_keys_json) if self.answer_keys_json else [],
            value_types=json.loads(self.value_types_json) if self.value_types_json else [],
            value_descriptions=json.loads(self.value_descriptions_json) if self.value_descriptions_json else [],
            answering_instructions=_deserialize_prompt_field(self.answering_instructions),
            question_presentation=_deserialize_prompt_field(self.question_presentation),
            include_comment=self.include_comment,
            permissive=self.permissive
        )

class QuestionYesNoMappedObject(QuestionMappedObject):
    __mapper_args__ = {
        'polymorphic_identity': 'yes_no',
    }
    edsl_class = QuestionYesNo

    @classmethod
    def from_edsl_object(cls, question: QuestionYesNo) -> QuestionYesNoMappedObject:
        db_question_instance = cls(
            question_name=question.question_name,
            question_text=question.question_text,
            answering_instructions=_serialize_prompt_field(question.answering_instructions),
            question_presentation=_serialize_prompt_field(question.question_presentation),
            include_comment=question.include_comment, 
            use_code=False, 
            permissive=getattr(question, 'permissive', False) 
        )
        current_options = question.question_options 
        db_question_instance.options_relation = [
            QuestionOptionMappedObject(option_value=str(opt_val)) for opt_val in current_options
        ]
        return db_question_instance

    def to_edsl_object(self) -> QuestionYesNo:
        options = [opt.option_value for opt in self.options_relation]
        return QuestionYesNo(
            question_name=self.question_name,
            question_text=self.question_text,
            question_options=options,
            answering_instructions=_deserialize_prompt_field(self.answering_instructions),
            question_presentation=_deserialize_prompt_field(self.question_presentation),
            include_comment=self.include_comment
        )

class QuestionTopKMappedObject(QuestionMappedObject):
    __mapper_args__ = {'polymorphic_identity': 'top_k'}
    edsl_class = QuestionTopK

    @classmethod
    def from_edsl_object(cls, question: QuestionTopK) -> QuestionTopKMappedObject:
        db_question_instance = cls(
            question_name=question.question_name,
            question_text=question.question_text,
            answering_instructions=_serialize_prompt_field(question.answering_instructions),
            question_presentation=_serialize_prompt_field(question.question_presentation),
            min_selections=question.min_selections,
            max_selections=question.max_selections,
            include_comment=question.include_comment, 
            use_code=question.use_code,             
            permissive=getattr(question, 'permissive', False) 
        )
        current_options = question.question_options
        db_question_instance.options_relation = [
            QuestionOptionMappedObject(option_value=str(opt_val)) for opt_val in current_options
        ]
        return db_question_instance

    def to_edsl_object(self) -> QuestionTopK:
        options = [opt.option_value for opt in self.options_relation]
        return QuestionTopK(
            question_name=self.question_name,
            question_text=self.question_text,
            question_options=options,
            min_selections=self.min_selections,
            max_selections=self.max_selections,
            answering_instructions=_deserialize_prompt_field(self.answering_instructions),
            question_presentation=_deserialize_prompt_field(self.question_presentation),
            include_comment=self.include_comment,
            use_code=self.use_code
        )

# Example usage (optional, for demonstration)
def example_sqlalchemy_usage():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    original_ft_question = QuestionFreeText(
        question_name="favorite_food",
        question_text="What is your favorite food?",
        answering_instructions=Prompt(text="Be brief and honest.") 
    )
    session.add(QuestionFreeTextMappedObject.from_edsl_object(original_ft_question))
    
    original_mc_question = QuestionMultipleChoice(
        question_name="preferred_activity",
        question_text="Which activity do you prefer?",
        question_options=["Reading", "Hiking", "Gaming"],
        include_comment=False 
    )
    session.add(QuestionMultipleChoiceMappedObject.from_edsl_object(original_mc_question))

    original_num_question = QuestionNumerical(
        question_name="estimated_age",
        question_text="How old is the Earth?",
        min_value=4.5e9,
        max_value=4.6e9,
        include_comment=True,
        permissive=False
    )
    session.add(QuestionNumericalMappedObject.from_edsl_object(original_num_question))
    
    original_list_question = QuestionList(
        question_name="grocery_items",
        question_text="What groceries do you need?",
        min_list_items=2,
        max_list_items=5,
        include_comment=True,
        permissive=False,
        answering_instructions="List up to 5 items."
    )
    session.add(QuestionListMappedObject.from_edsl_object(original_list_question))
    
    original_cb_question = QuestionCheckBox(
        question_name="preferred_languages",
        question_text="Which programming languages do you know?",
        question_options=["Python", "JavaScript", "SQL", "C++", "Java"],
        min_selections=1,
        max_selections=3,
        include_comment=True,
        use_code=False,
        permissive=False,
        answering_instructions="Select up to 3."
    )
    session.add(QuestionCheckBoxMappedObject.from_edsl_object(original_cb_question))
    
    original_dict_question = QuestionDict(
        question_name="user_profile",
        question_text="Provide user profile details.",
        answer_keys=["username", "email", "age"],
        value_types=["str", "str", "int"],
        value_descriptions=["Unique username", "Contact email", "Age in years"],
        include_comment=True,
        permissive=False
    )
    session.add(QuestionDictMappedObject.from_edsl_object(original_dict_question))
    
    original_yn_question = QuestionYesNo(
        question_name="is_sky_blue",
        question_text="Is the sky blue?",
        include_comment=False
    )
    session.add(QuestionYesNoMappedObject.from_edsl_object(original_yn_question))
    
    original_top_k_question = QuestionTopK(
        question_name="top_3_movies",
        question_text="Select your top 3 favorite movies from this list:",
        question_options=["Movie A", "Movie B", "Movie C", "Movie D", "Movie E"],
        min_selections=3,
        max_selections=3,
        include_comment=True,
        use_code=False
    )
    session.add(QuestionTopKMappedObject.from_edsl_object(original_top_k_question))
    
    session.commit()

    retrieved_sql_ft = session.query(QuestionFreeTextMappedObject).filter_by(question_name="favorite_food").first()
    if retrieved_sql_ft:
        retrieved_edsl_ft = retrieved_sql_ft.to_edsl_object()
        assert retrieved_edsl_ft.question_text == original_ft_question.question_text
        assert retrieved_edsl_ft.answering_instructions.text == original_ft_question.answering_instructions.text 
        print(f"FT OK: {retrieved_edsl_ft.question_name}")

    retrieved_sql_mc = session.query(QuestionMultipleChoiceMappedObject).filter_by(question_name="preferred_activity").first()
    if retrieved_sql_mc:
        retrieved_edsl_mc = retrieved_sql_mc.to_edsl_object()
        assert retrieved_edsl_mc.question_options == original_mc_question.question_options
        assert retrieved_edsl_mc._include_comment == original_mc_question._include_comment 
        assert retrieved_sql_mc.include_comment == original_mc_question._include_comment 
        print(f"MC OK: {retrieved_edsl_mc.question_name}, Include Comment: {retrieved_edsl_mc._include_comment}")

    retrieved_sql_num = session.query(QuestionNumericalMappedObject).filter_by(question_name="estimated_age").first()
    if retrieved_sql_num:
        retrieved_edsl_num = retrieved_sql_num.to_edsl_object()
        assert retrieved_edsl_num.min_value == original_num_question.min_value
        assert retrieved_edsl_num.max_value == original_num_question.max_value
        assert retrieved_edsl_num.include_comment == original_num_question.include_comment
        assert retrieved_sql_num.include_comment == original_num_question.include_comment 
        print(f"Num OK: {retrieved_edsl_num.question_name}, Min: {retrieved_edsl_num.min_value}")

    retrieved_sql_list = session.query(QuestionListMappedObject).filter_by(question_name="grocery_items").first()
    if retrieved_sql_list:
        retrieved_edsl_list = retrieved_sql_list.to_edsl_object()
        assert retrieved_edsl_list.min_list_items == original_list_question.min_list_items
        assert retrieved_edsl_list.max_list_items == original_list_question.max_list_items
        assert retrieved_edsl_list.include_comment == original_list_question.include_comment
        assert retrieved_sql_list.permissive == original_list_question.permissive
        print(f"List OK: {retrieved_edsl_list.question_name}, Min items: {retrieved_edsl_list.min_list_items}")

    retrieved_sql_cb = session.query(QuestionCheckBoxMappedObject).filter_by(question_name="preferred_languages").first()
    if retrieved_sql_cb:
        retrieved_edsl_cb = retrieved_sql_cb.to_edsl_object()
        assert retrieved_edsl_cb.question_options == original_cb_question.question_options
        assert retrieved_edsl_cb.min_selections == original_cb_question.min_selections
        assert retrieved_edsl_cb.max_selections == original_cb_question.max_selections
        assert retrieved_edsl_cb._include_comment == original_cb_question._include_comment 
        assert retrieved_edsl_cb._use_code == original_cb_question._use_code          
        assert retrieved_edsl_cb.permissive == original_cb_question.permissive
        print(f"CB OK: {retrieved_edsl_cb.question_name}, Min sel: {retrieved_edsl_cb.min_selections}")

    retrieved_sql_dict = session.query(QuestionDictMappedObject).filter_by(question_name="user_profile").first()
    if retrieved_sql_dict:
        retrieved_edsl_dict = retrieved_sql_dict.to_edsl_object()
        assert retrieved_edsl_dict.answer_keys == original_dict_question.answer_keys
        assert retrieved_edsl_dict.value_types == original_dict_question.value_types
        assert retrieved_edsl_dict.value_descriptions == original_dict_question.value_descriptions
        print(f"Dict OK: {retrieved_edsl_dict.question_name}")

    retrieved_sql_yn = session.query(QuestionYesNoMappedObject).filter_by(question_name="is_sky_blue").first()
    if retrieved_sql_yn:
        retrieved_edsl_yn = retrieved_sql_yn.to_edsl_object()
        assert retrieved_edsl_yn.question_options == original_yn_question.question_options
        assert retrieved_edsl_yn.include_comment == original_yn_question.include_comment
        assert retrieved_sql_yn.use_code == False 
        print(f"YesNo OK: {retrieved_edsl_yn.question_name}")

    retrieved_sql_top_k = session.query(QuestionTopKMappedObject).filter_by(question_name="top_3_movies").first()
    if retrieved_sql_top_k:
        retrieved_edsl_top_k = retrieved_sql_top_k.to_edsl_object()
        assert retrieved_edsl_top_k.question_options == original_top_k_question.question_options
        assert retrieved_edsl_top_k.min_selections == original_top_k_question.min_selections
        assert retrieved_edsl_top_k.max_selections == original_top_k_question.max_selections
        assert retrieved_edsl_top_k.use_code == original_top_k_question.use_code
        print(f"TopK OK: {retrieved_edsl_top_k.question_name}")

    all_questions_from_db = session.query(QuestionMappedObject).all()
    print(f"\nTotal questions in DB: {len(all_questions_from_db)}")
    for q_instance in all_questions_from_db:
        print(f"  - ID: {q_instance.id}, Name: {q_instance.question_name}, Type: {q_instance.question_type}")
        print(f"    DB values: include_comment={q_instance.include_comment}, permissive={q_instance.permissive}, use_code={q_instance.use_code}, min_val={q_instance.min_value}, min_list={q_instance.min_list_items}, min_sel={q_instance.min_selections}")

    session.close()

from sqlalchemy.schema import CreateTable

def print_sql_schema(engine):
    print("\n--- SQL Schema (Generated by SQLAlchemy) ---")
    for table in Base.metadata.sorted_tables:
        print(f"\n-- Table: {table.name}")
        print(CreateTable(table).compile(engine))
    print("--- End of SQL Schema ---")

if __name__ == "__main__":
    print("Running SQLAlchemy ORM example...")
    engine = create_engine('sqlite:///:memory:') 
    Base.metadata.create_all(engine)
    print_sql_schema(engine)
    
    print("\nRunning full example_sqlalchemy_usage now...")
    example_sqlalchemy_usage()
    print("SQLAlchemy ORM example completed.")
