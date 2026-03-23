from termcolor import colored


def _prefix(marker: str, show_marker: bool) -> str:
    return f"{marker} " if show_marker else ""


def error(message: str, show_emoji: bool = True) -> None:
    """
    Prints an error message.

    Args:
        message (str): The error message
        show_emoji (bool): Whether to show the prefix marker

    Returns:
        None
    """
    print(colored(f"{_prefix('[x]', show_emoji)}{message}", "red"))


def success(message: str, show_emoji: bool = True) -> None:
    """
    Prints a success message.

    Args:
        message (str): The success message
        show_emoji (bool): Whether to show the prefix marker

    Returns:
        None
    """
    print(colored(f"{_prefix('[+]', show_emoji)}{message}", "green"))


def info(message: str, show_emoji: bool = True) -> None:
    """
    Prints an info message.

    Args:
        message (str): The info message
        show_emoji (bool): Whether to show the prefix marker

    Returns:
        None
    """
    print(colored(f"{_prefix('[i]', show_emoji)}{message}", "magenta"))


def warning(message: str, show_emoji: bool = True) -> None:
    """
    Prints a warning message.

    Args:
        message (str): The warning message
        show_emoji (bool): Whether to show the prefix marker

    Returns:
        None
    """
    print(colored(f"{_prefix('[!]', show_emoji)}{message}", "yellow"))


def question(message: str, show_emoji: bool = True) -> str:
    """
    Prints a question message and returns the user's input.

    Args:
        message (str): The question message
        show_emoji (bool): Whether to show the prefix marker

    Returns:
        user_input (str): The user's input
    """
    return input(colored(f"{_prefix('[?]', show_emoji)}{message}", "magenta"))
