"""
SQLAlchemy ORM models for instructions in the EDSL framework.

This module defines database models for persisting Instruction and ChangeInstruction objects
using SQLAlchemy ORM.
"""

from typing import Optional, List, Dict, Any, Union, cast
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
import json

from .instruction import Instruction
from .change_instruction import ChangeInstruction
from .exceptions import InstructionError, InstructionValueError

Base = declarative_base()


class SQLInstruction(Base):
    """SQLAlchemy model for Instruction objects."""
    
    __tablename__ = "instructions"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    text = Column(String, nullable=False)
    preamble = Column(String, nullable=False, default="You were given the following instructions:")
    pseudo_index = Column(Float, nullable=False, default=0.0)
    
    # Single table inheritance
    type = Column(String(50))
    
    # Fields specific to ChangeInstruction
    keep = Column(JSON, nullable=True)
    drop = Column(JSON, nullable=True)
    
    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": "instruction"
    }
    
    def to_instruction(self) -> Instruction:
        """Convert SQLAlchemy model to domain Instruction object."""
        instruction = Instruction(
            name=self.name,
            text=self.text,
            preamble=self.preamble
        )
        instruction.pseudo_index = self.pseudo_index
        return instruction


class SQLChangeInstruction(SQLInstruction):
    """SQLAlchemy model for ChangeInstruction objects."""
    
    __mapper_args__ = {
        "polymorphic_identity": "change_instruction"
    }
    
    def to_instruction(self) -> ChangeInstruction:
        """Convert SQLAlchemy model to domain ChangeInstruction object."""
        if self.keep is None and self.drop is None:
            raise InstructionValueError("Keep and drop cannot both be None")
            
        keep_list = self.keep if self.keep is not None else []
        drop_list = self.drop if self.drop is not None else []
        
        change_instruction = ChangeInstruction(
            keep=keep_list,
            drop=drop_list
        )
        change_instruction.pseudo_index = self.pseudo_index
        
        # The name is initialized using add_name
        if hasattr(self, 'name') and self.name:
            # Extract index if the name follows the pattern, or use 0 as fallback
            if self.name.startswith("change_instruction_"):
                try:
                    index = int(self.name.replace("change_instruction_", ""))
                    change_instruction.add_name(index)
                except ValueError:
                    change_instruction.add_name(0)
            else:
                # For custom named change instructions, we need to manually set the name
                # as add_name would use the standard format
                change_instruction.name = self.name
            
        return change_instruction


def instruction_to_sql(instruction: Union[Instruction, ChangeInstruction]) -> SQLInstruction:
    """Convert a domain Instruction or ChangeInstruction to an SQLAlchemy model."""
    if isinstance(instruction, ChangeInstruction):
        sql_instruction = SQLChangeInstruction(
            name=instruction.name if hasattr(instruction, 'name') else f"change_instruction_{id(instruction)}",
            text="",  # ChangeInstruction doesn't have text, but the column is not nullable
            pseudo_index=instruction.pseudo_index,
            keep=instruction.keep,
            drop=instruction.drop
        )
    elif isinstance(instruction, Instruction):
        sql_instruction = SQLInstruction(
            name=instruction.name,
            text=instruction.text,
            preamble=instruction.preamble,
            pseudo_index=instruction.pseudo_index
        )
    else:
        raise InstructionValueError(f"Unknown instruction type: {type(instruction)}")
    
    return sql_instruction


def save_instruction(session: Session, instruction: Union[Instruction, ChangeInstruction]) -> SQLInstruction:
    """Save an Instruction or ChangeInstruction to the database."""
    sql_instruction = instruction_to_sql(instruction)
    
    # Check if the instruction already exists
    existing = session.query(SQLInstruction).filter_by(name=sql_instruction.name).first()
    if existing:
        # Update existing instruction
        for key, value in sql_instruction.__dict__.items():
            if not key.startswith('_') and key != 'id':
                setattr(existing, key, value)
        session.add(existing)
        sql_instruction = existing
    else:
        # Add new instruction
        session.add(sql_instruction)
    
    session.commit()
    return sql_instruction


def load_instruction(session: Session, name: str) -> Optional[Union[Instruction, ChangeInstruction]]:
    """Load an Instruction or ChangeInstruction from the database by name."""
    sql_instruction = session.query(SQLInstruction).filter_by(name=name).first()
    if sql_instruction is None:
        return None
    
    return sql_instruction.to_instruction()


def delete_instruction(session: Session, name: str) -> bool:
    """Delete an Instruction or ChangeInstruction from the database by name."""
    sql_instruction = session.query(SQLInstruction).filter_by(name=name).first()
    if sql_instruction is None:
        return False
    
    session.delete(sql_instruction)
    session.commit()
    return True