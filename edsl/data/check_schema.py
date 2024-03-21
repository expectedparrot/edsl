from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.schema import CreateTable
import difflib

# Assuming your ORM classes (LLMOutputDataDB and ResultDB) are defined as above
Base = declarative_base()

def schema_matches(db_uri, base=Base):

    from sqlalchemy import create_engine, MetaData

    # Replace 'your_database.db' with the path to your SQLite database file
    engine = create_engine(db_uri)

    # Reflect the database schema into a new MetaData object
    metadata = MetaData()
    metadata.reflect(bind=engine)

    # Replace 'your_table' with the name of your table
    table_name = 'responses'

    # Check if the table exists in the reflected metadata
    if table_name in metadata.tables:
        # Access the table
        table = metadata.tables[table_name]
        
        # Replace 'your_column' with the name of the column you're checking for
        column_name = 'iteration'
        
        # Check if the column exists in the table
        return column_name in table.columns
    else:
        return False

if __name__ == "__main__":

    # Example usage
    #db_uri = "sqlite:////bad_edsl_cache.db"
    import os
    db_uri = f"sqlite:///{os.path.join(os.getcwd(), 'bad_edsl_cache.db')}"
    if schema_matches(db_uri):
        print("The database schema matches the ORM.")
    else:
        print("The database schema does not match the ORM.")

# Example usage
#db_uri = "sqlite:///path_to_your_database.db"
#if schema_matches(db_uri):
#    print("The database schema matches the ORM.")
#else:
#    print("The database schema does not match the ORM.")
