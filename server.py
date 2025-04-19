import importlib
import sys
from typing import Awaitable, Dict, Callable, Type, Set

from aiohttp import web

from plugin import Plugin


class NameInUseError(ValueError):
    pass


class PluginNotLoaded(RuntimeError):
    pass


def _normalize_string_value(value: str):
    return value.strip().capitalize()


class Server(web.Application):
    """
    Subclass of aiohttp web.Application that contains all the command and webhook functionality
    """

    def __init__(self):
        super().__init__()

        # Initialize webhook route
        self.router.add_routes([
            web.post('/twitch_webhook', self._twitch_webhook_handler)
        ])

        # Initialize plugins
        self._commands: Dict[str, Callable[[dict], Awaitable]] = {}
        self._command_owners: Dict[str, str] = {}
        self._loaded_plugins: Dict[str, Type[Plugin]] = {}

    async def load_plugins(self, plugin_classes: list[Type[Plugin]]):
        for plugin_cls in plugin_classes:
            self._register_plugin_class(plugin_cls)

    def unload_plugin(self, plugin_name: str):
        """
        Unload a plugin based on its name.
        :param plugin_name: The class name of the plugin to unload
        :return:
        :raises PluginNotLoaded: Raised when the plugin is not loaded.
        """
        normalized_plugin_name = _normalize_string_value(plugin_name)
        if plugin_name not in self._loaded_plugins:
            raise PluginNotLoaded(f"Plugin '{plugin_name}' is not loaded.")

        to_remove: Set[str] = {
            command for command, owner in self._command_owners.items()
            if owner == normalized_plugin_name
        }

        for command in to_remove:
            del self._commands[command]
            del self._command_owners[command]

        del self._loaded_plugins[normalized_plugin_name]

    async def reload_plugin(self, plugin_name: str):
        """
        Reload a plugin based on its name.
        :param plugin_name:
        :return:
        """
        normalized_plugin_name = _normalize_string_value(plugin_name)
        plugin_cls = self._loaded_plugins.get(normalized_plugin_name)
        if not plugin_cls:
            raise PluginNotLoaded(f"Plugin '{plugin_name}' is not loaded.")

        module_path = plugin_cls.__module__
        if module_path in sys.modules:
            del sys.modules[module_path]

        module = importlib.import_module(module_path)
        importlib.reload(module)

        new_cls = getattr(module, normalized_plugin_name, None)
        if not new_cls:
            raise ImportError(f"Expected class '{plugin_name}' in module '{module_path}.")

        self.unload_plugin(plugin_cls.__name__)
        self._register_plugin_class(new_cls)

    def _register_command(self, plugin_name: str, name: str, func: Callable[[dict], Awaitable]):
        """
        Registers a command
        :param plugin_name: The name of the plugin that provides this command
        :param name: The name of the command
        :param func: Handler
        :return:
        """
        if name in self._commands:
            raise NameInUseError(f"Command name '{name}' is already registered by {self._command_owners[name]}.")
        self._commands[name] = func
        self._command_owners[name] = plugin_name

    def _register_plugin_class(self, plugin_cls: Type[Plugin]):
        """
        Register a plugin class.
        :param plugin_cls: The plugin class
        :return:
        """
        plugin_name = plugin_cls.__name__.lower()
        if plugin_name in self._loaded_plugins:
            raise NameInUseError(f"Plugin with name {plugin_name} is already loaded.")
        if not issubclass(plugin_cls, Plugin):
            raise TypeError(f"Plugin '{plugin_name}' must subclass Plugin.")

        for name, func in plugin_cls.plugin_commands.items():
            self._register_command(plugin_name, name, func)
        self._loaded_plugins[plugin_name] = plugin_cls

    async def _twitch_webhook_handler(self, request):
        # Utility coroutine, ONLY designates to correct place
        # Maybe later it's worth separating per event but no point currently
        raise NotImplementedError

    async def _twitch_chat_received(self, request):
        # Handles all twitch chat events by passing them to the correct command
        raise NotImplementedError

    async def _twitch_callback_verification_received(self, request):
        # Responds correctly to the twitch callback verification
        raise NotImplementedError

    async def _twitch_subscription_revocation_received(self, request):
        # Subscription was revoked - send a message to Discord webhook as this should not happen
        raise NotImplementedError
