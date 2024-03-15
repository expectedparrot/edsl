from __future__ import annotations
import enum

class TaskStatus(enum.Enum):
    "These are the possible statuses for a task."
    NOT_STARTED = enum.auto()
    WAITING_ON_DEPENDENCIES = enum.auto()
    CANCELLED = enum.auto()
    PARENT_FAILED = enum.auto()
    DEPENDENCIES_COMPLETE = enum.auto()
    WAITING_FOR_REQUEST_CAPCITY = enum.auto()
    REQUEST_CAPACITY_ACQUIRED = enum.auto()
    WAITING_FOR_TOKEN_CAPCITY = enum.auto()
    TOKEN_CAPACITY_ACQUIRED = enum.auto()
    API_CALL_IN_PROGRESS = enum.auto()
    API_CALL_COMPLETE = enum.auto()
    FINISHED = enum.auto()
    FAILED = enum.auto()

def get_enum_from_string(str_key):
    # Parse the string to extract the enum member name
    try:
        _, member_name = str_key.split('.')
        enum_member = getattr(TaskStatus, member_name)
        return enum_member
    except ValueError:
        return str_key


class TaskStatusDescriptor:
    "The descriptor ensures that the task status is always an instance of the TaskStatus enum."

    def __init__(self):
        self._task_status = None

    def __get__(self, instance, owner):
        return self._task_status

    def __set__(self, instance, value):
        """Ensure that the value is an instance of TaskStatus."""
        if not isinstance(value, TaskStatus):
            raise ValueError("Value must be an instance of TaskStatus enum")
        self._task_status = value

    def __delete__(self, instance):
        self._task_status = None

