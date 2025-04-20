import inspect
from typing import Callable, Dict


def command(name: str = None):
    """
    Enables usage of @command decorator.
    If no variable is passed, the function name is treated as the command.
    Otherwise, the passed string is used.
    """

    def decorator(func: Callable):
        func_name = name
        if func_name is None:
            func_name = func.__name__
        setattr(func, "__is_command__", True)
        setattr(func, "__command_name__", func_name.lower())
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

    def on_ready(self):
        """
        Called once when all plugins are loaded.
        :return:
        """
        pass

    def on_load(self):
        """
        Called whenever this plugin is loaded.
        :return:
        """
        pass

    def on_unload(self):
        """
        Called whenever this plugin is unloaded.
        :return:
        """
        pass


class CommandIsNotCoroutineError(TypeError):
    pass
