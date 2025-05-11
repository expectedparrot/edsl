import tempfile
import os
from uuid import UUID
import uuid

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, func, insert

from sqlalchemy import event
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

# --- imports -------------------------------------------------------------
import uuid
from typing import Any, Type, Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    event,
    UniqueConstraint,
)

from sqlalchemy.dialects.postgresql import UUID            # use Generic type if not on PG
from sqlalchemy.orm import (
    Session,
)

class Base(DeclarativeBase):
    _registry: dict[str, type] = {}
    _table_registry: dict[str, type] = {}
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

            # Enforce that any ORM class tying to an EDSL class is UUID-aware
            if not issubclass(cls, UUIDTrackable):
                raise TypeError(
                    f"{cls.__name__} sets 'edsl_class' but does not inherit from UUIDTrackable"
                )

        # Additional registry keyed by SQLAlchemy __tablename__
        if hasattr(cls, "__tablename__"):
            Base._table_registry[getattr(cls, "__tablename__")] = cls

    @classmethod
    def create_orm(cls, edsl_object: Any, existing_uuid: Optional[UUID] = None):
        """Return a newly-constructed ORM instance corresponding to *edsl_object*.

        The method consults the internal ``_edsl_registry`` that maps an
        EDSL class to the name of the ORM class which declared it in its
        ``edsl_class`` attribute.  Once the appropriate ORM class is
        located, its ``from_edsl_object`` constructor is called and the
        resulting instance returned.

        Additional *args* / *kwargs* are forwarded verbatim to
        ``from_edsl_object`` because some conversions may require extra
        context (e.g. a *name* for an ``AgentListMappedObject``).
        """
        # 1. Try an exact match first -------------------------------------------------
        orm_cls_name = cls._edsl_registry.get(edsl_object.__class__)

        # 2. Fallback to *isinstance* checks for subclass relationships ------------
        if orm_cls_name is None:
            for registered_edsl_cls, mapped_name in cls._edsl_registry.items():
                if isinstance(edsl_object, registered_edsl_cls):
                    orm_cls_name = mapped_name
                    break

        if orm_cls_name is None:
            raise ValueError(
                f"No ORM class registered for EDSL object of type {edsl_object.__class__.__name__}."
            )

        # 3. Resolve the ORM class object ------------------------------------------
        orm_cls = cls._registry.get(orm_cls_name)
        if orm_cls is None:
            raise RuntimeError(
                f"Registry corruption: ORM class name '{orm_cls_name}' not found in _registry."
            )

        # 4. Ensure the target class implements the expected factory ---------------
        from_edsl = getattr(orm_cls, "from_edsl_object", None)
        if not callable(from_edsl):
            raise AttributeError(
                f"ORM class {orm_cls.__name__} does not implement a callable 'from_edsl_object' method."
            )

        # 5. Delegate instance construction and return -----------------------------
        object = from_edsl(edsl_object)
        if existing_uuid is not None:
            object.uuid = existing_uuid
        return object

def create_orm(edsl_object, existing_uuid: Optional[UUID] = None):
    return Base.create_orm(edsl_object, existing_uuid=existing_uuid)

class UUIDLookup(Base):
    """
    One row for every persistent object that participates
    in the global UUID namespace.
      uuid         – primary key for external references
      object_type  – __tablename__ of the real table
      object_id    – PK in the real table
    """
    __tablename__ = "uuid_lookup"
    edsl_class = None

    uuid: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    object_type: Mapped[str] = mapped_column(String, nullable=False)
    object_id:   Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("object_type", "object_id", name="uq_lookup_object"),
    )

    # handy resolver ------------------------------------------------------
    @staticmethod
    def resolve(session: Session, uuid_: UUID | str) -> Any | None:
        """Retrieve the real mapped object associated with *uuid_*.

        The lookup table stores *object_type* as the SQLAlchemy ``__tablename__``
        of the original mapped class.  ``Base.registry._class_registry``
        (and our own ``Base._registry``) are both keyed by **class names**, so a
        direct dictionary access can fail.  We therefore:

        1. Normalise *uuid_* to a ``uuid.UUID`` instance.
        2. Look up the row in ``uuid_lookup``.
        3. Try to fetch the mapped class straight from the registry using the
           stored key.
        4. If that fails, fall back to scanning the registry for a class whose
           ``__tablename__`` matches *object_type*.
        """
        # Accept strings as well as UUID instances
        if isinstance(uuid_, str):
            uuid_ = UUID(uuid_)

        # 1. Look up the helper row
        row = session.get(UUIDLookup, uuid_)
        if row is None:
            return None

        object_type = row.object_type  # stored table name (e.g. "agent")
        object_id = row.object_id

        # Quick lookup via table name
        target_cls: Type[Base] | None = Base._table_registry.get(object_type)

        if target_cls is None:
            # Mapping not loaded – could happen if the module defining the
            # class hasn't been imported yet.
            return None
            
        # Handle special case for Question classes that use Single Table Inheritance
        if object_type == 'question':
            # First try to directly query for the object with the right UUID to get the correct subclass
            from sqlalchemy import text
            stmt = text("SELECT question_type FROM question WHERE id = :id")
            result = session.execute(stmt, {"id": object_id}).fetchone()
            if result and result[0]:
                discriminator_value = result[0]  # Get the discriminator value (question_type)
                
                # Find the right class based on the discriminator value
                for class_name, cls in Base._registry.items():
                    if (hasattr(cls, '__mapper_args__') and 
                        cls.__mapper_args__.get('polymorphic_identity') == discriminator_value):
                        target_cls = cls
                        break
        
        # Handle special case for Instruction classes that use Single Table Inheritance
        elif object_type == 'instruction':
            # First try to directly query for the object with the right UUID to get the correct subclass
            from sqlalchemy import text
            stmt = text("SELECT instruction_type FROM instruction WHERE id = :id")
            result = session.execute(stmt, {"id": object_id}).fetchone()
            if result and result[0]:
                discriminator_value = result[0]  # Get the discriminator value (instruction_type)
                
                # Find the right class based on the discriminator value
                for class_name, cls in Base._registry.items():
                    if (hasattr(cls, '__mapper_args__') and 
                        cls.__mapper_args__.get('polymorphic_identity') == discriminator_value):
                        target_cls = cls
                        break

        # Return the real object
        return session.get(target_cls, row.object_id)


class UUIDTrackable:
    """
    Add this mix-in to any mapped class that should be addressable by UUID.
    """
    uuid: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True
    )


# # --- 4) EVENT HANDLER ----------------------------------------------------
# @event.listens_for(Session, "after_flush")
# def _create_lookup_rows(session: Session, flush_context):
#     """
#     Runs once per flush; examines freshly-added objects that inherit
#     from UUIDTrackable and adds a corresponding UUIDLookup row.
#     """
#     for obj in session.new:
#         if isinstance(obj, UUIDTrackable):
#             session.add(
#                 UUIDLookup(
#                     uuid=obj.uuid,
#                     object_type=obj.__tablename__,
#                     object_id=obj.id,          # PK is populated by now
#                 )
#             )


@event.listens_for(Session, "after_flush")
def _register_new_objects(session, flush_context):
    for obj in session.new:
        if not isinstance(obj, UUIDTrackable):
            continue

        values = dict(
            uuid=obj.uuid,
            object_type=obj.__tablename__,
            object_id=obj.id,
        )

        if session.bind.dialect.name == "sqlite":
            stmt = (
                sqlite_insert(UUIDLookup)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["uuid"])
            )
        else:   # "postgresql"
            stmt = (
                pg_insert(UUIDLookup)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["uuid"])
            )

        session.execute(stmt)


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
