"""Utilities for dftly libraries."""


def validate_dict_keys(
    mapping: dict,
    required: set[str] | None = None,
    allowed: set[str] | None = None,
) -> tuple[set[str], set[str]]:
    """Returns any missing required keys (first) and any extra unallowed keys (second).

    Args:
        mapping: The dictionary to validate.
        required: A set of required keys. If omitted, no keys are required.
        allowed: A set of allowed, but not required keys. If omitted, no additional keys are allowed.

    Returns:
        A tuple of two sets: (missing required keys, extra disallowed keys)

    Raises:
        TypeError: If `mapping` is not a dictionary.

    Examples:
        >>> validate_dict_keys({'a': 1, 'b': 2}, required={'a'}, allowed={'a', 'b', 'c'})
        (set(), set())

    If a required key is missing, it will be reported:

        >>> validate_dict_keys({'a': 1}, required={'a', 'b'}, allowed={'c'})
        ({'b'}, set())

    Extra keys will be reported if they are not in the allowed set:

        >>> validate_dict_keys({'a': 1, 'b': 2, 'd': 4}, required={'a'}, allowed={'b', 'c'})
        (set(), {'d'})

    None can be used to indicate no required or additional allowed keys. Note that all required keys are
    considered allowed.

        >>> validate_dict_keys({'a': 1, 'b': 2, 'd': 4}, required=None, allowed={'a', 'b', 'c'})
        (set(), {'d'})
        >>> validate_dict_keys({'a': 1, 'b': 2}, required={'a'}, allowed=None)
        (set(), {'b'})

    There is no issue if allowed and required intersect:

        >>> validate_dict_keys({'a': 1, 'b': 2}, required={'a'}, allowed={'a', 'b', 'c'})
        (set(), set())

    Errors will be raised if the input is not a dictionary:

        >>> validate_dict_keys(['a', 'b'], required={'a'}, allowed={'b', 'c'})
        Traceback (most recent call last):
            ...
        TypeError: mapping must be a dictionary; got list
    """

    if not isinstance(mapping, dict):
        raise TypeError(f"mapping must be a dictionary; got {type(mapping).__name__}")

    required = required or set()
    allowed = (allowed or set()) | required

    keys = set(mapping.keys())
    missing = required - keys
    extra = keys - allowed if allowed else keys - required

    return missing, extra
