from sqlalchemy import Column, String, Integer, Text, Index, Sequence
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class LLMOutputDataDB(Base):
    __tablename__ = "responses"

    # Primary key
    id = Column(Integer, Sequence("response_id_seq"), primary_key=True)

    # Fields
    model = Column(String(100), nullable=False)
    parameters = Column(Text, nullable=False)
    system_prompt = Column(Text, nullable=False)
    prompt = Column(Text, nullable=False)
    output = Column(Text, nullable=False)

    # Index for faster queries
    idx_responses_fields = Index(
        "idx_responses_fields", "prompt", "system_prompt", "model", "parameters"
    )
