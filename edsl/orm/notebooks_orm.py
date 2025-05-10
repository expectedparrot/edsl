from sqlalchemy import JSON, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional, Dict, Any

from ..notebooks import Notebook
from .sql_base import Base, TimestampMixin


class NotebookMappedObject(Base, TimestampMixin):
    __tablename__ = "notebooks"  # Table name, e.g., "notebooks"
    edsl_class = Notebook

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data: Mapped[Dict[str, Any]] = mapped_column(JSON)
    lint: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    @classmethod
    def from_edsl_object(cls, edsl_object: 'Notebook') -> 'NotebookMappedObject':
        """Converts an EDSL Notebook object to a NotebookMappedObject."""
        notebook_dict = edsl_object.to_dict(add_edsl_version=False)
        # The to_dict already provides name, data, lint directly
        return cls(
            name=notebook_dict.get("name"),
            data=notebook_dict.get("data"),
            lint=notebook_dict.get("lint", True) # Ensure lint has a default if not in dict
        )

    def to_edsl_object(self) -> 'Notebook':
        """Converts the ORM object back to an EDSL Notebook object."""
        # Notebook.from_dict expects 'name' and 'data', and can take 'lint'
        return Notebook.from_dict({
            "name": self.name,
            "data": self.data,
            "lint": self.lint
        })

    @classmethod
    def example(cls) -> 'NotebookMappedObject':
        """Creates an example NotebookMappedObject from an EDSL Notebook example."""
        example_notebook = Notebook.example()
        return cls.from_edsl_object(example_notebook)

    def __repr__(self) -> str:
        return f"NotebookMappedObject(id={self.id}, name='{self.name}', lint={self.lint})"


if __name__ == "__main__":
    from .sql_base import create_test_session
    from ..notebooks import Notebook # EDSL Notebook

    # Create an example EDSL Notebook
    example_edsl_notebook = Notebook.example()
    print(f"Original EDSL Notebook: {example_edsl_notebook.name}, Lint: {example_edsl_notebook.lint}")

    # Convert to ORM object
    notebook_orm = NotebookMappedObject.from_edsl_object(example_edsl_notebook)
    print(f"Notebook ORM object (before commit): {notebook_orm.name}, Lint: {notebook_orm.lint}")

    # Setup test database session
    db, _, _ = create_test_session()

    # Add to session, commit, and refresh
    db.add(notebook_orm)
    db.commit()
    db.refresh(notebook_orm)
    print(f"Created Notebook in DB: {notebook_orm}")

    # Retrieve the notebook
    retrieved_notebook_orm = db.query(NotebookMappedObject).filter(NotebookMappedObject.id == notebook_orm.id).first()
    if retrieved_notebook_orm:
        print(f"Retrieved Notebook ORM: {retrieved_notebook_orm.name}, Created at: {retrieved_notebook_orm.created_at}, Lint: {retrieved_notebook_orm.lint}")

        # Convert back to EDSL object
        reconstituted_edsl_notebook = retrieved_notebook_orm.to_edsl_object()
        print(f"Reconstituted EDSL Notebook: {reconstituted_edsl_notebook.name}, Lint: {reconstituted_edsl_notebook.lint}")

        # Verify equality
        # Note: Notebook.__eq__ checks self.data == other.data.
        # Name and lint are not part of __eq__ but are important for ORM.
        if example_edsl_notebook == reconstituted_edsl_notebook:
            print("Original and reconstituted EDSL Notebooks' data are equal.")
        else:
            print("Original and reconstituted EDSL Notebooks' data are NOT equal.")
            # For more detailed comparison:
            # print("Original data:", example_edsl_notebook.data)
            # print("Reconstituted data:", reconstituted_edsl_notebook.data)

        assert example_edsl_notebook.name == reconstituted_edsl_notebook.name
        assert example_edsl_notebook.lint == reconstituted_edsl_notebook.lint
        print("Name and lint attributes also match.")
    else:
        print("Failed to retrieve notebook from DB.")

    db.close()
    print("Notebook ORM test finished.") 