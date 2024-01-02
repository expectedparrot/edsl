class DatabaseErrors(Exception):
    pass


class DatabaseConnectionError(DatabaseErrors):
    pass


class DatabaseCRUDError(DatabaseErrors):
    pass
