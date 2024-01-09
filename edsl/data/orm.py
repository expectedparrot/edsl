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


class ResultDB(Base):
    __tablename__ = "result"

    id = Column(Integer, primary_key=True)
    job_uuid = Column(String, nullable=False)
    result_uuid = Column(String, nullable=False)
    agent = Column(Text, nullable=False)
    scenario = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    idx_job_uuid = Index("idx_job_uuid", "job_uuid")
