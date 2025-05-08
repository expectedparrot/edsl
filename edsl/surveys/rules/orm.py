"""SQLAlchemy ORM models for Rule and RuleCollection."""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, JSON, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from typing import Optional, List, Dict, Any, Union
import json

from ..base import EndOfSurvey

Base = declarative_base()

class SQLRule(Base):
    """SQLAlchemy ORM model for Rule."""
    
    __tablename__ = "rules"
    
    id = Column(Integer, primary_key=True)
    current_q = Column(Integer, nullable=False)
    expression = Column(String, nullable=False)
    next_q = Column(String, nullable=False)  # Can be int or "EndOfSurvey"
    priority = Column(Integer, nullable=False)
    before_rule = Column(Boolean, default=False)
    question_name_to_index = Column(JSON, nullable=False)
    
    # Foreign key relationship to SQLRuleCollection
    rule_collection_id = Column(Integer, ForeignKey("rule_collections.id"), nullable=False)
    rule_collection = relationship("SQLRuleCollection", back_populates="rules")
    
    def __repr__(self):
        """Return string representation of the rule."""
        return f'SQLRule(id={self.id}, current_q={self.current_q}, expression="{self.expression}", next_q={self.next_q}, priority={self.priority}, before_rule={self.before_rule})'
    
    def to_model(self) -> 'Rule':
        """Convert ORM object to Rule model instance."""
        from .rule import Rule
        
        # Handle EndOfSurvey case
        next_q_value = EndOfSurvey if self.next_q == "EndOfSurvey" else int(self.next_q)
        
        # Create Rule instance
        return Rule(
            current_q=self.current_q,
            expression=self.expression,
            next_q=next_q_value,
            question_name_to_index=self.question_name_to_index,
            priority=self.priority,
            before_rule=self.before_rule,
        )
    
    @classmethod
    def from_model(cls, rule, rule_collection_id: int) -> 'SQLRule':
        """Create ORM object from Rule model instance."""
        next_q = "EndOfSurvey" if rule.next_q == EndOfSurvey else rule.next_q
        
        return cls(
            current_q=rule.current_q,
            expression=rule.expression,
            next_q=next_q,
            priority=rule.priority,
            before_rule=rule.before_rule,
            question_name_to_index=rule.question_name_to_index,
            rule_collection_id=rule_collection_id
        )


class SQLRuleCollection(Base):
    """SQLAlchemy ORM model for RuleCollection."""
    
    __tablename__ = "rule_collections"
    
    id = Column(Integer, primary_key=True)
    num_questions = Column(Integer, nullable=True)
    survey_id = Column(Integer, nullable=True)  # Optional reference to survey
    
    # Relationship to rules
    rules = relationship("SQLRule", back_populates="rule_collection", cascade="all, delete-orphan")
    
    def __repr__(self):
        """Return string representation of the RuleCollection."""
        return f"SQLRuleCollection(id={self.id}, num_questions={self.num_questions}, rules_count={len(self.rules)})"

    def to_model(self) -> 'RuleCollection':
        """Convert ORM object to RuleCollection model instance."""
        from .rule_collection import RuleCollection
        
        # Convert all rules to model instances
        rule_models = [rule.to_model() for rule in self.rules]
        
        # Create RuleCollection instance
        return RuleCollection(
            num_questions=self.num_questions,
            rules=rule_models
        )
    
    @classmethod
    def from_model(cls, rule_collection, survey_id: Optional[int] = None) -> 'SQLRuleCollection':
        """Create ORM object from RuleCollection model instance."""
        # Create the SQLRuleCollection instance without rules first
        rule_collection_orm = cls(
            num_questions=rule_collection.num_questions,
            survey_id=survey_id
        )
        
        # We need to save this instance to get an ID before adding rules
        # This would typically be done in the actual database transaction
        # For now, we'll return it without the rules and let the caller handle this
        
        return rule_collection_orm
    
    def add_rules_from_model(self, rule_collection):
        """Add rules from a model RuleCollection to this ORM instance."""
        for rule in rule_collection:
            rule_orm = SQLRule.from_model(rule, self.id)
            self.rules.append(rule_orm)


# Helper functions for database operations

def save_rule_collection(session, rule_collection, survey_id=None) -> SQLRuleCollection:
    """Save a RuleCollection to the database."""
    # Create ORM object
    rule_collection_orm = SQLRuleCollection.from_model(rule_collection, survey_id)
    
    # Add to session and flush to get ID
    session.add(rule_collection_orm)
    session.flush()
    
    # Now add all the rules
    rule_collection_orm.add_rules_from_model(rule_collection)
    
    return rule_collection_orm

def load_rule_collection(session, rule_collection_id) -> 'RuleCollection':
    """Load a RuleCollection from the database by ID."""
    rule_collection_orm = session.query(SQLRuleCollection).get(rule_collection_id)
    if rule_collection_orm:
        return rule_collection_orm.to_model()
    return None

def delete_rule_collection(session, rule_collection_id) -> bool:
    """Delete a RuleCollection from the database."""
    rule_collection_orm = session.query(SQLRuleCollection).get(rule_collection_id)
    if rule_collection_orm:
        session.delete(rule_collection_orm)
        return True
    return False