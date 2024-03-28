"""This module contains the Database class, which manages the connection to the database."""
import os
import shutil
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.exc import SQLAlchemyError, DatabaseError
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.sql import text
from edsl.config import Config, CONFIG
from edsl.data import Base
from edsl.exceptions import DatabaseConnectionError, DatabaseIntegrityError

from edsl.data.check_schema import schema_matches
import shutil 

class Database:
    """Manage the connection to the database."""

    def __init__(self, config: Config = CONFIG):
        """Initialize the database connection."""
        self.database_path = config.get("EDSL_DATABASE_PATH")
        try:
            self.engine = create_engine(self.database_path)

            # Check if the database schema matches the ORM
            file_name = self.database_path.split("/")[-1]
            if file_name is "edsl_cache.db" and not schema_matches(self.database_path):
                self.engine.dispose()

                database_file_path = self.database_path.replace('sqlite:///', '')

                backup_path = database_file_path + ".bak"

                #raise DatabaseIntegrityError(
                #    "The database schema does not match the ORM. "
                #    "Please update your database schema."
                #)
                print("The database schema does not match the ORM. Making a backup of the database and deleting the original.")
                print("The back is at ", backup_path)
                shutil.copy(database_file_path,backup_path)
                os.remove(database_file_path)
                self.engine = create_engine(self.database_path)
                

            # listener sets WAL mode on connect
            # @event.listens_for(self.engine, "connect")
            # def set_wal_mode(dbapi_connection, connection_record):
            #     cursor = dbapi_connection.cursor()
            #     cursor.execute("PRAGMA journal_mode=WAL;")
            #     cursor.close()

            # test connection
            with self.engine.connect() as _:
                pass
            Base.metadata.create_all(bind=self.engine)
        except DatabaseError as e:
            if "malformed" in str(e):
                file_path, temp_path = self.paths
                if temp_path and os.path.exists(temp_path):
                    raise DatabaseIntegrityError(
                        f"Your database is malformed. "
                        f"Try replacing your main database file with the temp copy.\n"
                        f"Database file: {file_path}\n"
                        f"Temp file: {temp_path}"
                    )
                else:
                    raise DatabaseIntegrityError(
                        f"Your database is malformed. "
                        f"Please delete your database file.\n"
                        f"Database file: {file_path}\n"
                    )

        except SQLAlchemyError as e:
            raise DatabaseConnectionError(str(e)) from None
        self.SessionLocal = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        )

    @contextmanager
    def get_db(self):
        """Generate a database session."""
        db = None
        try:
            db = self.SessionLocal()
            yield db
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(str(e)) from None
        finally:
            if db is not None:
                self.SessionLocal.remove()

    def _is_healthy(self):
        """Return True if the database is healthy, False otherwise."""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text("PRAGMA integrity_check"))
                check_result = result.fetchone()
                if check_result[0] == "ok":
                    return True
                else:
                    return False
        except SQLAlchemyError as e:
            return False

    @property
    def paths(self) -> tuple:
        """Return the (db_path, temp_path), or (None, None) if not applicable."""
        if (
            self.database_path.startswith("sqlite:///")
            and "memory" not in self.database_path
        ):
            file_path = self.database_path.replace("sqlite:///", "")
            temp_path = f"{file_path}_temp"
            return file_path, temp_path
        else:
            return None, None

    def _create_copy(self) -> None:
        """Create a copy of the database."""
        file_path, temp_path = self.paths
        if file_path:
            try:
                shutil.copyfile(file_path, temp_path)
            except IOError as e:
                print(f"Error creating a copy of the database: {e}")
                raise e

    def _delete_copy(self) -> None:
        """Delete a copy of the database."""
        file_path, temp_path = self.paths
        if file_path and os.path.exists(temp_path):
            os.remove(temp_path)

    def _health_check_pre_run(self):
        """Perform a health check before running a job."""
        # create a copy of the database if it is healthy
        if self._is_healthy():
            self._create_copy()
        else:
            file_path, temp_path = self.paths
            raise DatabaseIntegrityError(
                f"Could not run job because your database is not healthy.\n"
                f"Try replacing your main database file with the temp copy.\n"
                f"Database file: {file_path}\n"
                f"Temp file: {temp_path}"
            )

    def _health_check_post_run(self):
        """Perform a health check before running a job."""
        if self._is_healthy():
            self._delete_copy()
        else:
            file_path, temp_path = self.paths
            print(
                f"Running this job malformed your database.\n"
                f"Try replacing your main database file with the temp copy.\n"
                f"Database file: {file_path}\n"
                f"Temp file: {temp_path}"
            )


# Note: Python modules are singletons. As such, once `database` is imported
# the same instance of it is reused across the application.
database = Database()
