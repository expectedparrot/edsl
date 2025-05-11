import pytest
from edsl.orm.sql_base import Base, create_test_session, UUIDLookup

from edsl.orm import load_orm_classes
load_orm_classes()

@pytest.fixture
def db_session():
    """Create a test database session."""
    session, _, _ = create_test_session()
    yield session
    session.close()


def get_orm_classes():
    """Get all registered ORM classes that have an edsl_class."""
    classes = []
    for class_name in Base._registry.keys():
        cls = Base._registry[class_name]
        if cls.edsl_class is not None:
            classes.append(pytest.param(cls, id=class_name))
    return classes


@pytest.mark.parametrize("cls", get_orm_classes())
def test_orm_object_insertion(db_session, cls):
    """Test that the specified ORM class can create and insert an example object."""
    class_name = cls.__name__
    
    # Create example object
    example = cls.edsl_class.example()
    assert example is not None, f"Failed to create example for {class_name}"
    
    # Convert to ORM object
    orm_obj = cls.from_edsl_object(example)
    assert orm_obj is not None, f"Failed to convert {class_name} example to ORM object"
    
    # Test database insertion
    db_session.add(orm_obj)
    db_session.commit()
    
    # Verify the object was inserted correctly
    db_session.refresh(orm_obj)
    assert orm_obj.id is not None, f"Failed to insert {class_name} into database"
    
    # Convert original to EDSL object before clearing session
    original_edsl = cls.to_edsl_object(orm_obj)
    
    # Store the ID
    obj_id = orm_obj.id
    
    # Clear session to ensure we're fetching from DB
    db_session.expunge_all()
    
    # Fetch the object from the database
    fetched_obj = db_session.query(cls).filter(cls.id == obj_id).first()
    assert fetched_obj is not None, f"Failed to fetch {class_name} from database"
    
    # Convert fetched to EDSL object and compare
    fetched_edsl = cls.to_edsl_object(fetched_obj)
    
    # Assert they are equivalent
    assert original_edsl == fetched_edsl, f"Fetched {class_name} doesn't match original"


@pytest.mark.parametrize("cls", get_orm_classes())
def test_orm_object_uuid_retrieval(db_session, cls):
    """Test that ORM objects can be retrieved by UUID after insertion."""
    class_name = cls.__name__
    
    # Create example object
    example = cls.edsl_class.example()
    assert example is not None, f"Failed to create example for {class_name}"
    
    # Convert to ORM object
    orm_obj = cls.from_edsl_object(example)
    assert orm_obj is not None, f"Failed to convert {class_name} example to ORM object"
    
    # Test database insertion
    db_session.add(orm_obj)
    db_session.commit()
    
    # Verify the object was inserted correctly
    db_session.refresh(orm_obj)
    assert orm_obj.id is not None, f"Failed to insert {class_name} into database"
    
    # Get the UUID from the ORM object
    if not hasattr(orm_obj, 'uuid'):
        pytest.skip(f"{class_name} doesn't have a uuid attribute")
    
    uuid = orm_obj.uuid
    assert uuid is not None, f"{class_name} has a uuid attribute but it's None"
    
    # Convert original to EDSL object before clearing session
    original_edsl = cls.to_edsl_object(orm_obj)
    
    # Clear session to ensure we're fetching from DB
    db_session.expunge_all()
    
    # Fetch the object from the database using UUID
    fetched_obj = db_session.query(cls).filter(cls.uuid == uuid).first()
    assert fetched_obj is not None, f"Failed to fetch {class_name} from database using UUID"
    
    # Convert fetched to EDSL object and compare
    fetched_edsl = cls.to_edsl_object(fetched_obj)
    
    # Assert they are equivalent
    assert original_edsl == fetched_edsl, f"UUID-fetched {class_name} doesn't match original"


@pytest.mark.parametrize("cls", get_orm_classes())
def test_uuid_lookup_table_retrieval(db_session, cls):
    """Test that ORM objects can be retrieved using the UUIDLookup table."""
    class_name = cls.__name__
    
    # Create example object
    example = cls.edsl_class.example()
    assert example is not None, f"Failed to create example for {class_name}"
    
    # Convert to ORM object
    orm_obj = cls.from_edsl_object(example)
    assert orm_obj is not None, f"Failed to convert {class_name} example to ORM object"
    
    # Test database insertion
    db_session.add(orm_obj)
    db_session.commit()
    
    # Verify the object was inserted correctly
    db_session.refresh(orm_obj)
    assert orm_obj.id is not None, f"Failed to insert {class_name} into database"
    
    # Get the UUID from the ORM object
    if not hasattr(orm_obj, 'uuid'):
        pytest.skip(f"{class_name} doesn't have a uuid attribute")
    
    uuid = orm_obj.uuid
    assert uuid is not None, f"{class_name} has a uuid attribute but it's None"
    
    # Convert original to EDSL object before clearing session
    original_edsl = cls.to_edsl_object(orm_obj)
    
    # First verify the UUIDLookup entry exists
    from edsl.orm.sql_base import UUIDLookup
    lookup_entry = db_session.query(UUIDLookup).filter(UUIDLookup.uuid == uuid).first()
    assert lookup_entry is not None, f"No entry in UUIDLookup table for {class_name} UUID: {uuid}"
    
    # Store information for debugging
    table_name = orm_obj.__tablename__
    obj_id = orm_obj.id
    lookup_table = lookup_entry.object_type
    lookup_id = lookup_entry.object_id
    
    # Clear session to ensure we're fetching from DB
    db_session.expunge_all()
    
    # Directly try to resolve first to see what we get
    direct_fetch = db_session.query(cls).filter(cls.uuid == uuid).first()
    
    # Fetch the object using UUIDLookup.resolve
    fetched_obj = UUIDLookup.resolve(db_session, uuid)
    
    # Detailed error if lookup fails
    if fetched_obj is None:
        error_msg = f"""
Failed to fetch {class_name} using UUIDLookup.resolve with UUID: {uuid}
Object info:
- Table name: {table_name}
- Object ID: {obj_id}
UUIDLookup entry:
- Lookup table: {lookup_table}
- Lookup ID: {lookup_id}
Direct query result: {"Found" if direct_fetch else "Not found"}
"""
        assert fetched_obj is not None, error_msg
    
    assert isinstance(fetched_obj, cls), f"UUIDLookup.resolve returned wrong type: {type(fetched_obj)} instead of {cls}"
    
    # Convert fetched to EDSL object and compare
    fetched_edsl = cls.to_edsl_object(fetched_obj)
    
    # Assert they are equivalent
    assert original_edsl == fetched_edsl, f"UUIDLookup-fetched {class_name} doesn't match original"


@pytest.mark.parametrize("cls", get_orm_classes())
def test_uuid_lookup_table_debug(db_session, cls):
    """Debug test to check the UUIDLookup table entries."""
    class_name = cls.__name__
    
    # Create example object
    example = cls.edsl_class.example()
    assert example is not None, f"Failed to create example for {class_name}"
    
    # Convert to ORM object
    orm_obj = cls.from_edsl_object(example)
    assert orm_obj is not None, f"Failed to convert {class_name} example to ORM object"
    
    # Test database insertion
    db_session.add(orm_obj)
    db_session.commit()
    
    # Verify the object was inserted correctly
    db_session.refresh(orm_obj)
    assert orm_obj.id is not None, f"Failed to insert {class_name} into database"
    
    # Get the UUID from the ORM object
    if not hasattr(orm_obj, 'uuid'):
        pytest.skip(f"{class_name} doesn't have a uuid attribute")
    
    uuid = orm_obj.uuid
    assert uuid is not None, f"{class_name} has a uuid attribute but it's None"
    
    # Check if there's an entry in UUIDLookup table
    from edsl.orm.sql_base import UUIDLookup
    lookup_entry = db_session.query(UUIDLookup).filter(UUIDLookup.uuid == uuid).first()
    
    assert lookup_entry is not None, f"No entry in UUIDLookup table for {class_name} UUID: {uuid}"
    
    # Check if the correct table name and ID are stored
    assert lookup_entry.object_type == orm_obj.__tablename__, f"Wrong object_type in UUIDLookup: {lookup_entry.object_type} != {orm_obj.__tablename__}"
    assert lookup_entry.object_id == orm_obj.id, f"Wrong object_id in UUIDLookup: {lookup_entry.object_id} != {orm_obj.id}"


@pytest.mark.parametrize("cls", get_orm_classes())
def test_debug_uuid_lookup_issue(db_session, cls, capfd):
    """Debug test to understand why UUIDLookup.resolve isn't working for Question classes."""
    class_name = cls.__name__
    
    if not class_name == "QuestionFreeTextMappedObject":
        pytest.skip(f"Skipping non-target class: {class_name}")
    
    # Create example object
    example = cls.edsl_class.example()
    assert example is not None, f"Failed to create example for {class_name}"
    
    # Convert to ORM object
    orm_obj = cls.from_edsl_object(example)
    assert orm_obj is not None, f"Failed to convert {class_name} example to ORM object"
    
    # Test database insertion
    db_session.add(orm_obj)
    db_session.commit()
    
    # Verify the object was inserted correctly
    db_session.refresh(orm_obj)
    assert orm_obj.id is not None, f"Failed to insert {class_name} into database"
    
    # Get the UUID from the ORM object
    if not hasattr(orm_obj, 'uuid'):
        pytest.skip(f"{class_name} doesn't have a uuid attribute")
    
    uuid = orm_obj.uuid
    assert uuid is not None, f"{class_name} has a uuid attribute but it's None"
    
    # Use sys.stdout directly to ensure output is captured
    import sys
    
    sys.stdout.write(f"==== Testing with {class_name} ====\n")
    sys.stdout.write(f"Created object: {orm_obj}\n")
    sys.stdout.write(f"UUID: {uuid}\n")
    sys.stdout.write(f"Table name: {orm_obj.__tablename__}\n")
    sys.stdout.write(f"ID: {orm_obj.id}\n")
    sys.stdout.write(f"Class name: {orm_obj.__class__.__name__}\n")
    
    # First verify the UUIDLookup entry exists
    from edsl.orm.sql_base import UUIDLookup
    
    lookup_entry = db_session.query(UUIDLookup).filter(UUIDLookup.uuid == uuid).first()
    assert lookup_entry is not None, f"No entry in UUIDLookup table for {class_name} UUID: {uuid}"
    
    sys.stdout.write(f"UUIDLookup entry found: {lookup_entry.__dict__}\n")
    
    # Clear session to ensure we're fetching from DB
    db_session.expunge_all()
    
    # Try direct method
    direct_fetch = db_session.query(cls).filter(cls.uuid == uuid).first()
    sys.stdout.write(f"Direct query result: {direct_fetch}\n")
    
    # Debug lookup via table registry
    sys.stdout.write(f"Available tables in registry:\n")
    for k, v in Base._table_registry.items():
        sys.stdout.write(f"  - {k}: {v.__name__}\n")
    
    # Look for Question's table in the registry
    table_name = lookup_entry.object_type
    target_cls = Base._table_registry.get(table_name)
    sys.stdout.write(f"Looking up table '{table_name}' in registry: {target_cls.__name__ if target_cls else None}\n")
    
    # Manually try to resolve
    if target_cls:
        target_obj = db_session.get(target_cls, lookup_entry.object_id)
        sys.stdout.write(f"Manual get result: {target_obj}\n")
        sys.stdout.write(f"Manual get class: {target_obj.__class__.__name__ if target_obj else None}\n")
        
        # Check if this is the right subclass
        sys.stdout.write(f"Is target_obj instance of {cls.__name__}? {isinstance(target_obj, cls)}\n")
    
    # Now try UUIDLookup.resolve
    sys.stdout.write("Now trying UUIDLookup.resolve...\n")
    resolved_obj = UUIDLookup.resolve(db_session, uuid)
    sys.stdout.write(f"UUIDLookup.resolve result: {resolved_obj}\n")
    
    # Force output to be displayed
    sys.stdout.flush()
    out, err = capfd.readouterr()
    sys.stdout.write(out)
    sys.stderr.write(err)
    
    # No assert here - we're just debugging
