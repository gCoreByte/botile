import importlib
import os
import sys
from enum import Enum
from typing import Awaitable, Dict, Callable, Type, Set

from aiohttp import web

from plugin import Plugin

class CallbackType(Enum):
    ON_READY = "on_ready"
    ON_LOAD = "on_load"
    ON_UNLOAD = "on_unload"

class TwitchNotificationType(Enum):
    NOTIFICATION = "notification"
    WEBHOOK_CALLBACK_VERIFICATION = "webhook_callback_verification"
    REVOCATION = "revocation"


class NameInUseError(ValueError):
    pass


class PluginNotLoaded(RuntimeError):
    pass


def _normalize_string_value(value: str):
    return value.strip().lower()


def _wrap_method(instance: Plugin, method: Callable) -> Callable[[dict], Awaitable]:
    # TODO: Add context object
    async def wrapper(context):
        return await method(instance, context)
    return wrapper


def _perform_lifecycle_callback(instance: Plugin, callback: CallbackType):
    if hasattr(instance, callback.value):
        getattr(instance, callback.value)()


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
        self._plugin_instances: Dict[str, Plugin] = {}

        self.on_cleanup.append(self._revoke_subscriptions)

    async def load_plugins(self, plugin_classes: list[Type[Plugin]]):
        for plugin_cls in plugin_classes:
            self._register_plugin_class(plugin_cls)

        # Lifecycle callback
        for plugin_instance in self._plugin_instances.values():
            _perform_lifecycle_callback(plugin_instance, CallbackType.ON_READY)

    def unload_plugin(self, plugin_name: str):
        """
        Unload a plugin based on its name.
        :param plugin_name: The class name of the plugin to unload
        :return:
        :raises PluginNotLoaded: Raised when the plugin is not loaded.
        """
        normalized_plugin_name = _normalize_string_value(plugin_name)
        plugin_cls = self._loaded_plugins.get(normalized_plugin_name)
        if not plugin_cls:
            raise PluginNotLoaded(f"Plugin '{plugin_name}' is not loaded.")

        # Lifecycle callback
        instance = self._plugin_instances.get(normalized_plugin_name)
        _perform_lifecycle_callback(instance, CallbackType.ON_UNLOAD)

        to_remove: Set[str] = {
            command for command, owner in self._command_owners.items()
            if owner == normalized_plugin_name
        }

        for command in to_remove:
            del self._commands[command]
            del self._command_owners[command]

        del self._loaded_plugins[normalized_plugin_name]
        del self._plugin_instances[normalized_plugin_name]

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
        plugin_name = _normalize_string_value(plugin_cls.__name__)
        if plugin_name in self._loaded_plugins:
            raise NameInUseError(f"Plugin with name {plugin_name} is already loaded.")
        if not issubclass(plugin_cls, Plugin):
            raise TypeError(f"Plugin '{plugin_name}' must subclass Plugin.")

        instance = plugin_cls()
        for name, func in plugin_cls.plugin_commands.items():
            self._register_command(plugin_name, name, _wrap_method(instance, func))

        # Lifecycle callback
        _perform_lifecycle_callback(instance, CallbackType.ON_LOAD)

        self._loaded_plugins[plugin_name] = plugin_cls
        self._plugin_instances[plugin_name] = instance

    async def _twitch_webhook_handler(self, request: web.Request) -> web.Response:
        """
        Sends the request to the correct handler.
        :param request:
        :return:
        """
        # We need to process these within a few seconds. If performance becomes an issue we can store these temporarily,
        # respond 200 fast and then process in the background.
        match request.headers["Twitch-Eventsub-Message-Type"]:
            case TwitchNotificationType.NOTIFICATION.value:
                return await self._twitch_notification_received(request)
            case TwitchNotificationType.WEBHOOK_CALLBACK_VERIFICATION.value:
                return await self._twitch_callback_verification_received(request)
            case TwitchNotificationType.REVOCATION.value:
                return await self._twitch_subscription_revocation_received(request)

    async def _twitch_notification_received(self, request: web.Request) -> web.Response:
        """
        Sends the notification to the correct handler.
        :param request:
        :return: web.
        """
        # For now lets just send them directly to the chat handler - can refactor later when needed.
        json = await request.json()
        return await self._twitch_chat_received(json["event"])


    async def _twitch_chat_received(self, context: Dict) -> web.Response:
        """
        Passes the received message to the corresponding handler alongside the context.
        :param context:
        :return web.Response:
        """
        command = _normalize_string_value(context["message"]["text"]).split()[0]
        # Not a command, return fast
        if not command.startswith("!"):
            return web.Response(status=200)
        command = command.removeprefix("!")
        handler = self._commands.get(command)
        if handler:
          await handler(context)
        return web.Response(status=200)

    async def _twitch_callback_verification_received(self, request: web.Request) -> web.Response:
        """
        Responds to twitch challenges.
        :param request:
        :return:
        """
        json = await request.json()
        print("[Twitch] Responding to challenge...")
        return web.Response(status=200, text=json["challenge"], content_type="text/plain")

    async def _twitch_subscription_revocation_received(self, request):
        # Subscription was revoked - send a message to Discord webhook as this should not happen
        raise NotImplementedError

    async def _revoke_subscriptions(self, app):
        raise NotImplementedError

