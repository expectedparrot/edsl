import keyword


def is_valid_variable_name(name, allow_name=True):
    """Check if a string is a valid variable name."""
    if allow_name:
        return name.isidentifier() and not keyword.iskeyword(name)
    else:
        return (
            name.isidentifier() and not keyword.iskeyword(name) and not name == "name"
        )
