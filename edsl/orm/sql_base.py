import tempfile
import os

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, func

class Base(DeclarativeBase):
    _registry = {}
    _edsl_registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._registry[cls.__name__] = cls

        if not hasattr(cls, "edsl_class"):
            raise AttributeError(
                f"Class {cls.__name__} must define an 'edsl_class' attribute."
            )

        edsl_class_value = getattr(cls, "edsl_class")
        if edsl_class_value is not None:
            Base._edsl_registry[edsl_class_value] = cls.__name__

class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps to a model."""
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), nullable=False)
    # updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


def create_test_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    # Import EDSL classes for the main example block
    # from edsl import Agent, AgentList # Ensure AgentList is imported - these are now at the top

    # Create a temporary directory that will persist
    # The user is responsible for cleaning this up later if desired.
    tmpdir = tempfile.mkdtemp(prefix='edsl_db_')
    db_path = os.path.join(tmpdir, "data.db")
    print(f"SQLite database created at: {db_path}")
    print(f"NOTE: This directory and database WILL NOT be automatically cleaned up.")
    print(f"You can manually delete the directory: {tmpdir}")

    # Define database engine to use the file-based SQLite database
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    return db, db_path, tmpdir
