from sqlalchemy import Column, Integer, Text, JSON, DateTime, func, ForeignKey, String, Boolean, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import Optional, Dict, Any, List

from ..language_models.language_model import LanguageModel
from ..language_models.model_list import ModelList

from .sql_base import Base, TimestampMixin, UUIDTrackable


class ModelParameter(Base):
    __tablename__ = "language_model_parameters"
    edsl_class = None
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("language_model.id"))
    key: Mapped[str] = mapped_column()
    value: Mapped[Any] = mapped_column(JSON)  # Using JSON for flexibility in parameter values

    model: Mapped["LanguageModelMappedObject"] = relationship(back_populates="parameters")

    def __repr__(self):
        return f"ModelParameter(id={self.id}, key='{self.key}', value='{self.value}')"


class LanguageModelMappedObject(Base, TimestampMixin, UUIDTrackable):
    __tablename__ = "language_model"
    edsl_class = LanguageModel

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    model_name: Mapped[str] = mapped_column()
    inference_service: Mapped[str] = mapped_column()
    remote: Mapped[bool] = mapped_column(default=False)
    rpm: Mapped[Optional[float]] = mapped_column(nullable=True)
    tpm: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    parameters: Mapped[List["ModelParameter"]] = relationship("ModelParameter", back_populates="model", cascade="all, delete-orphan")
    
    # Foreign key and relationship for ModelList
    model_list_id: Mapped[Optional[int]] = mapped_column(ForeignKey("model_list.id"), nullable=True)
    model_list: Mapped[Optional["ModelListMappedObject"]] = relationship(back_populates="models")

    @classmethod
    def from_edsl_object(cls, edsl_object: 'LanguageModel'):
        """Convert a LanguageModel domain object to a LanguageModelMappedObject."""
        data = edsl_object.to_dict(add_edsl_version=False)
        
        # Extract parameters from the model
        parameter_items = []
        if 'parameters' in data and isinstance(data['parameters'], dict):
            for key, value in data['parameters'].items():
                parameter_items.append(ModelParameter(key=key, value=value))
        
        # Remove parameters dict as it will be handled by relationship
        parameters = data.pop('parameters', {})
        
        # Extract other fields
        model_name = data.pop('model', '')
        inference_service = data.pop('inference_service', '')
        
        # Create ORM model object
        return cls(
            model_name=model_name,
            inference_service=inference_service,
            parameters=parameter_items,
            remote=getattr(edsl_object, 'remote', False)
        )
    
    def to_edsl_object(self) -> 'LanguageModel':
        """Converts the ORM object back to an EDSL LanguageModel object."""
        # Reconstruct parameters dictionary from ModelParameter objects
        parameters_dict = {param.key: param.value for param in self.parameters or []}
        
        # Import here to avoid circular imports
        from ..language_models.language_model import LanguageModel
        from ..language_models.model import Model
        
        # Use the Model factory to create the appropriate LanguageModel subclass
        model_params = {
            "model": self.model_name,
            "service_name": self.inference_service,
            **parameters_dict
        }
        
        # Add rate limits if set
        if self.rpm is not None:
            model_params["rpm"] = self.rpm
        
        if self.tpm is not None:
            model_params["tpm"] = self.tpm
        
        # Create model instance
        model = Model(**model_params)
        
        # Set remote flag if applicable
        if self.remote:
            model.remote = True
        
        return model
    
    @classmethod
    def example(cls) -> 'LanguageModelMappedObject':
        """Create an example LanguageModelMappedObject for testing."""
        from ..language_models.language_model import LanguageModel
        return cls.from_edsl_object(LanguageModel.example())

    def __repr__(self) -> str:
        return f"LanguageModelMappedObject(id={self.id}, model_name='{self.model_name}', service='{self.inference_service}')"


class ModelListMappedObject(Base, TimestampMixin, UUIDTrackable):
    __tablename__ = "model_list"
    edsl_class = ModelList

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Optional name for the list

    # Relationship to LanguageModelMappedObject: A ModelList has many LanguageModels
    models: Mapped[List["LanguageModelMappedObject"]] = relationship(
        "LanguageModelMappedObject", 
        back_populates="model_list", 
        cascade="all, delete-orphan"
    )

    @classmethod
    def from_edsl_object(cls, edsl_model_list: 'ModelList', name: Optional[str] = None) -> 'ModelListMappedObject':
        """
        Converts an EDSL ModelList object into a ModelListMappedObject ORM object.
        This method does not commit it to the session; that's the caller's responsibility.
        """
        mapped_models = []
        if edsl_model_list:
            for model_edsl in edsl_model_list:
                model_mapped = LanguageModelMappedObject.from_edsl_object(model_edsl)
                mapped_models.append(model_mapped)
            
        return cls(name=name, models=mapped_models)

    def to_edsl_object(self) -> 'ModelList':
        """
        Converts this ModelListMappedObject ORM object back into an EDSL ModelList object.
        """
        from ..language_models.model_list import ModelList
        
        model_list = ModelList()
        if self.models:
            for model_mapped in self.models:
                model_edsl = model_mapped.to_edsl_object()
                model_list.append(model_edsl)
        
        return model_list

    def __repr__(self) -> str:
        num_models = len(self.models) if self.models else 0
        return f"ModelListMappedObject(id={self.id}, name='{self.name}', num_models={num_models})"


if __name__ == "__main__":
    from .sql_base import create_test_session
    
    from ..language_models.language_model import LanguageModel
    from ..language_models.model import Model
    from ..language_models.model_list import ModelList

    # Test creating and retrieving a LanguageModel
    test_model = Model.example()
    new_model_orm = LanguageModelMappedObject.from_edsl_object(test_model)
    db, _, _ = create_test_session()

    db.add(new_model_orm)
    db.commit()
    db.refresh(new_model_orm)

    print(f"Created model: {new_model_orm}")

    retrieved_model = db.query(LanguageModelMappedObject).filter(
        LanguageModelMappedObject.model_name == test_model.model
    ).first()
    
    if retrieved_model:
        print(f"Retrieved model: {retrieved_model}")
        print(f"Created at: {retrieved_model.created_at}")
        print("Parameters:")
        for param in retrieved_model.parameters:
            print(f"  {param.key}: {param.value} (created at: {param.created_at})")
    
    # Test ModelList
    print("\n--- Testing ModelListMappedObject ---")
    
    # Create an EDSL ModelList
    example_model_list = ModelList.example()
    print(f"Original EDSL ModelList: {example_model_list}")
    
    # Convert to ModelListMappedObject
    model_list_orm = ModelListMappedObject.from_edsl_object(example_model_list, name="ExampleModelList")
    
    # Add to DB, commit, refresh
    db.add(model_list_orm)
    db.commit()
    db.refresh(model_list_orm)
    print(f"Created ModelListMappedObject: {model_list_orm}")
    
    # Retrieve the ModelListMappedObject from DB
    retrieved_model_list_orm = db.query(ModelListMappedObject).filter(
        ModelListMappedObject.name == "ExampleModelList"
    ).first()
    
    if retrieved_model_list_orm:
        print(f"Retrieved ModelListMappedObject: {retrieved_model_list_orm}")
        print(f"Created at: {retrieved_model_list_orm.created_at}")
        print(f"Number of models: {len(retrieved_model_list_orm.models)}")
        
        # Convert back to EDSL ModelList
        reconstituted_model_list = retrieved_model_list_orm.to_edsl_object()
        print(f"Reconstituted EDSL ModelList: {reconstituted_model_list}")
        
        # Verify equality
        if len(reconstituted_model_list) == len(example_model_list):
            print("Original and reconstituted EDSL ModelLists have the same length.")
        
        if example_model_list.to_dict(add_edsl_version=False) == reconstituted_model_list.to_dict(add_edsl_version=False):
            print("Original and reconstituted EDSL ModelLists have the same content.")
    
    db.close()