import inspect
from typing import Callable, Dict


def command(name: str = None):
    """
    Enables usage of @command decorator.
    If no variable is passed, the function name is treated as the command.
    Otherwise, the passed string is used.
    """

    def decorator(func: Callable):
        setattr(func, "__is_command__", True)
        setattr(func, "__command_name__", name or func.__name__)
        return func

    return decorator


class PluginMeta(type):
    def __new__(cls, name, bases, attrs):
        commands: Dict[str, Callable] = {}

        for key, value in attrs.items():
            if callable(value) and getattr(value, "__is_command__", False):
                if not inspect.iscoroutinefunction(value):
                    raise CommandIsNotCoroutineError(f"Command '{key}' must be an async function.")
                command_name = getattr(value, "__command_name__", key)
                commands[command_name] = value

            attrs["plugin_commands"] = commands
            return super().__new__(cls, name, bases, attrs)


class Plugin(metaclass=PluginMeta):
    """Base class for all plugins."""
    plugin_commands: Dict[str, Callable]
    pass


class CommandIsNotCoroutineError(TypeError):
    pass
