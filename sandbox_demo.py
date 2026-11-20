"""Tiny module used only to give the sandbox pull request something to summarise."""


def greet(name: str) -> str:
    if not name:
        raise ValueError("name must not be empty")
    return f"Hello, {name}!"


def farewell(name: str) -> str:
    return f"Goodbye, {name}!"
