"""SQLAlchemy ORM models for Rule and RuleCollection using SQLAlchemy 2.0 style."""

from sqlalchemy import Integer, String, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List, Dict, Any, Union

from ..surveys.base import EndOfSurvey

# Import the shared Base
from .sql_base import Base

# Forward declaration for EDSL type hints
if False:  # TYPE_CHECKING replacement for models not yet defined
    from ..rules.rule import Rule
    from ..rules.rule_collection import RuleCollection


class RuleMappedObject(Base):
    """SQLAlchemy ORM model for a Rule, compatible with SQLAlchemy 2.0."""
    
    __tablename__ = "rule"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    current_q: Mapped[int] = mapped_column(Integer, nullable=False)
    expression: Mapped[str] = mapped_column(String, nullable=False)
    next_q: Mapped[str] = mapped_column(String, nullable=False)  # Stores int or "EndOfSurvey" as string
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    before_rule: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    question_name_to_index: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    
    # Foreign key relationship to RuleCollectionMappedObject
    rule_collection_id: Mapped[int] = mapped_column(ForeignKey("rule_collections.id"), nullable=False)
    rule_collection: Mapped["RuleCollectionMappedObject"] = relationship(back_populates="rules")
    
    def __repr__(self) -> str:
        """Return string representation of the rule."""
        return f'RuleMappedObject(id={self.id}, current_q={self.current_q}, expression="{self.expression}", next_q="{self.next_q}", priority={self.priority}, before_rule={self.before_rule})'
    
    def to_edsl_object(self) -> 'Rule':
        """Convert ORM object to EDSL Rule model instance."""
        from ..surveys.rules.rule import Rule  # Assuming EDSL Rule path
        
        next_q_value: Union[int, EndOfSurvey.__class__]
        if self.next_q == "EndOfSurvey":
            next_q_value = EndOfSurvey
        else:
            try:
                next_q_value = int(self.next_q)
            except ValueError:
                # This case should ideally not happen if data is clean
                raise ValueError(f"Invalid next_q value in database for rule id {self.id}: '{self.next_q}'")
        
        return Rule(
            current_q=self.current_q,
            expression=self.expression,
            next_q=next_q_value,
            question_name_to_index=self.question_name_to_index,
            priority=self.priority,
            before_rule=self.before_rule,
        )
    
    @classmethod
    def from_edsl_object(cls, edsl_rule: 'Rule') -> "RuleMappedObject":
        """Create ORM object from EDSL Rule model instance."""
        # rule_collection_id is not passed here; SQLAlchemy handles it via relationship
        next_q_str = "EndOfSurvey" if edsl_rule.next_q is EndOfSurvey else str(edsl_rule.next_q)
        
        return cls(
            current_q=edsl_rule.current_q,
            expression=edsl_rule.expression,
            next_q=next_q_str,
            priority=edsl_rule.priority,
            before_rule=edsl_rule.before_rule,
            question_name_to_index=edsl_rule.question_name_to_index,
        )


class RuleCollectionMappedObject(Base):
    """SQLAlchemy ORM model for a RuleCollection, compatible with SQLAlchemy 2.0."""
    
    __tablename__ = "rule_collections"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    num_questions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Relationship to rules
    rules: Mapped[List["RuleMappedObject"]] = relationship(
        "RuleMappedObject", 
        back_populates="rule_collection", 
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        """Return string representation of the RuleCollection."""
        rules_count = len(self.rules) if self.rules else 0
        return f"RuleCollectionMappedObject(id={self.id}, num_questions={self.num_questions}, rules_count={rules_count})"

    @classmethod
    def from_edsl_object(cls, edsl_rc: 'RuleCollection') -> "RuleCollectionMappedObject":
        """Creates an ORM RuleCollectionMappedObject from an EDSL RuleCollection."""
        mapped_rules = []
        # Directly access edsl_rc.rules, assuming it exists and is iterable
        for edsl_rule_obj in edsl_rc: # Iterate over the collection object itself
            mapped_rules.append(RuleMappedObject.from_edsl_object(edsl_rule_obj))
        
        return cls(
            num_questions=edsl_rc.num_questions, # Directly access num_questions
            rules=mapped_rules
        )

    def to_edsl_object(self) -> 'RuleCollection':
        """Converts this ORM RuleCollectionMappedObject back to an EDSL RuleCollection."""
        from ..surveys.rules.rule_collection import RuleCollection # Assuming EDSL RuleCollection path

        edsl_rules_list = [mapped_rule.to_edsl_object() for mapped_rule in self.rules or []]
        
        # Directly initialize EDSL RuleCollection, assuming constructor handles these arguments.
        # This will raise an error if the constructor signature is different or 
        # if attributes are missing from self.
        return RuleCollection(
            rules=edsl_rules_list,
            num_questions=self.num_questions
        )


if __name__ == "__main__":
    from .sql_base import create_test_session
    from ..surveys.rules.rule import Rule  # EDSL Rule
    from ..surveys.rules.rule_collection import RuleCollection  # EDSL RuleCollection
    # ORM classes RuleMappedObject and RuleCollectionMappedObject are defined in the current file.

    print("\n--- Testing RuleCollectionMappedObject: Save and Fetch ---")

    # 1. Create an EDSL RuleCollection example
    example_rc_edsl = RuleCollection.example()
    print(example_rc_edsl)
    print(f"Original EDSL RuleCollection created with {len(list(example_rc_edsl))} rules.")

    # 2. Convert to RuleCollectionMappedObject
    rc_orm = RuleCollectionMappedObject.from_edsl_object(example_rc_edsl)

    # 3. Get a DB session
    db, _, _ = create_test_session()
    
    saved_rc_id = None

    db.add(rc_orm)
    db.commit()
    db.refresh(rc_orm)
    saved_rc_id = rc_orm.id
    rules_count_after_save = len(rc_orm.rules) if rc_orm.rules else 0
    print(f"Saved RuleCollectionMappedObject to DB with ID: {saved_rc_id} and {rules_count_after_save} rules.")

        # 5. Fetch it back from the database
    retrieved_rc_orm = db.query(RuleCollectionMappedObject).filter(RuleCollectionMappedObject.id == saved_rc_id).first()
    