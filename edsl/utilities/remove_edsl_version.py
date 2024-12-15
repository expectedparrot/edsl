from functools import wraps


def remove_edsl_version(func):
    """
    Decorator for the EDSL objects' `from_dict` method.
    - Removes the EDSL version and class name from the dictionary.
    - Ensures backwards compatibility with older versions of EDSL.
    """

    @wraps(func)
    def wrapper(cls, data, *args, **kwargs):
        data_copy = dict(data)
        edsl_version = data_copy.pop("edsl_version", None)
        edsl_classname = data_copy.pop("edsl_class_name", None)

        # Version- and class-specific logic here
        if edsl_classname == "Survey":
            if edsl_version is None or edsl_version <= "0.1.20":
                data_copy["question_groups"] = {}

        return func(cls, data_copy, *args, **kwargs)

    return wrapper
