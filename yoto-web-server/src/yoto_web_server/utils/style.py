def classnames(
    *args: str | tuple[str, bool] | tuple[bool, str] | dict[str, bool],
    **kwargs: bool,
) -> str:
    """Utility function to build class names conditionally.

    Args:
        *args: Positional arguments which can be:
            - str: A class name to include.
            - tuple[str, bool]: A class name and a boolean indicating whether to include it.
            - tuple[bool, str]: A boolean and a class name indicating whether to include it.
            - dict[str, bool]: A dictionary mapping class names to booleans indicating whether to include them.
        **kwargs: Keyword arguments mapping class names to booleans indicating whether to include them.

    Returns:
        str: A space-separated string of class names to include.
    """
    classes = []

    for arg in args:
        if isinstance(arg, str):
            classes.append(arg)
        elif isinstance(arg, tuple) and len(arg) == 2:
            arg0, arg1 = arg
            if isinstance(arg0, str) and isinstance(arg1, bool):
                class_name, include = arg
            elif isinstance(arg0, bool) and isinstance(arg1, str):
                include, class_name = arg
            else:
                continue
            if include:
                classes.append(class_name)
        elif isinstance(arg, dict):
            for class_name, include in arg.items():
                if include:
                    classes.append(class_name)

    for class_name, include in kwargs.items():
        if include:
            classes.append(class_name)

    return " ".join(classes)
