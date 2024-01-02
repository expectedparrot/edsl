from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, scoped_session
from edsl.config import Config, CONFIG
from edsl.data import Base
from edsl.exceptions import DatabaseConnectionError


class Database:
    """The Database class manages the connection to the database."""

    def __init__(self, config: Config = CONFIG):
        """Initializes the database connection."""
        database_path = config.get("EDSL_DATABASE_PATH")
        try:
            self.engine = create_engine(database_path)
            with self.engine.connect() as _:
                pass
            Base.metadata.create_all(bind=self.engine)
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(str(e)) from None
        self.SessionLocal = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        )

    @contextmanager
    def get_db(self):
        """Generator that yields a database session."""
        db = None
        try:
            db = self.SessionLocal()
            yield db
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(str(e)) from None
        finally:
            if db is not None:
                self.SessionLocal.remove()


# Note: Python modules are singletons. As such, once `database` is imported
# the same instance of it is reused across the application.
database = Database()
