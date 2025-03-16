from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import (
    safe_builtins,
    guarded_iter_unpack_sequence,
)


def guarded_iter(obj, allowed_types=(list, tuple, set, dict, range)):
    """Ensures iteration is only performed on safe, allowable types."""
    if not isinstance(obj, allowed_types):
        raise TypeError(f"Iteration over {type(obj).__name__} not allowed.")
    return iter(obj)


class FunctionAForbiddenAttributeException(Exception):
    """Exception for errors during function execution when forbidden key is used."""


def default_guarded_getitem(ob, key):
    sensitive_python_keys = [
        "__dict__",
        "__class__",
        "__module__",
        "__bases__",
        "__mro__",
        "__subclasses__",
        "__func__",
        "__self__",
        "__closure__",
        "__code__",
        "__globals__",
        "__call__",
        "__getattr__",
        "__getattribute__",
        "__delattr__",
        "__setattr__",
    ]
    if key in sensitive_python_keys:
        raise FunctionAForbiddenAttributeException(
            f"Access denied for attribute: {key}"
        )

    return ob.get(key)


def create_restricted_function(function_name, source_code, loop_activated=True):
    """Activate the function using RestrictedPython with basic restrictions."""
    safe_env = safe_globals.copy()
    safe_env["__builtins__"] = {**safe_builtins}
    safe_env["_getitem_"] = default_guarded_getitem

    if loop_activated:
        safe_env["_getiter_"] = guarded_iter
        safe_env["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence

    tmp_source_code = source_code.split("def ")
    if len(tmp_source_code) >= 2:
        source_code = "def " + tmp_source_code[1]

    byte_code = compile_restricted(source_code, "<string>", "exec")
    loc = {}
    try:
        exec(byte_code, safe_env, loc)
        func = loc[function_name]
    except Exception as e:
        print("Creating restricted function error:", e)
        raise e

    return func
