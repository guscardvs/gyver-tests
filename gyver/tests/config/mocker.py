from contextlib import contextmanager
from typing import Any, Callable, Sequence

from gyver.config.provider import ConfigLoader, ProviderConfig, ProviderT

from .registry import config_map


class ConfigMocker:
    """
    ConfigMocker is a context manager for mocking provider configurations.
    It allows to mock and use registered providers in a controlled environment
    and revert them to their original behavior when the context is exited."""

    def __init__(
        self,
        *custom_factories: tuple[type[ProviderT], Callable[[], ProviderT]],
    ) -> None:
        """
        :param custom_factories: a list of custom factories, that will override
                                existing factories with the same config class
        """
        self.factories: dict[
            type[ProviderConfig], Callable[[], ProviderConfig]
        ] = config_map | dict(custom_factories)
        self._resolved: dict[type[ProviderConfig], ProviderConfig] = {}

    def resolve(self, config_class: type[ProviderConfig]) -> None:
        """
        Resolve an instance of a config class using its registered factory
        """
        self._resolved[config_class] = self.factories[config_class]()

    def resolve_all(self, only: Sequence[type[ProviderConfig]] = ()):
        """
        Resolve all config classes, or the classes
        passed as the `only` argument
        :param only: a list of classes to resolve, the others will be ignored
        """
        to_resolve = self.factories
        if only:
            to_resolve = {
                key: value for key, value in self.factories.items() if key in only
            }
        if not set(self.factories).difference(self._resolved):
            return
        for config_class in to_resolve:
            if config_class in self._resolved:
                continue
            self.resolve(config_class)

    def unresolve(self):
        """
        Unresolve all config classes
        """
        self._resolved.clear()

    def register(self, config_class: type[ProviderT], factory: Callable[[], ProviderT]):
        """
        Register a new factory for a config class
        :param config_class: the config class to register the factory for
        :param factory: the factory to use when resolving the config class
        """
        self.factories[config_class] = factory

    def get(self, config_class: type[ProviderT]) -> ProviderT:
        """
        Get an instance of the config class, resolving it if necessary
        :param config_class: the config class to get the instance of
        :returns: an instance of the config class
        """
        if config_class not in self.factories:
            raise ValueError(f"No factory registered for {config_class}")
        try:
            return self._resolved[config_class]  # type: ignore
        except KeyError:
            self.resolve(config_class)
            return self._resolved[config_class]  # type: ignore

    @contextmanager
    def mock(self, only: Sequence[type[ProviderConfig]] = ()):
        """A context manager to mock the specified configurations

        This context manager mocks the specified configuration classes,
        so that they return the registered instances when used.
        The mocked classes are returned to their original state
        when the context manager exits.

        :param only(Sequence[type[ProviderConfig]], optional): A sequence of
        configuration classes to be mocked. If left empty, all the registered
        configuration classes will be mocked.

        :yields: No value is returned.
        """
        self.resolve_all(only)
        classmethods_map = {key: (key.__new__, key.__init__) for key in self._resolved}
        custom_init = make_custom_method(None)
        for config_class, instance in self._resolved.items():
            config_class.__new__ = make_custom_method(instance)
            config_class.__init__ = custom_init

        get = self.get

        def _mocked_load(
            self: ConfigLoader,
            model_cls: type[ProviderConfig],
            **presets: Any,
        ):
            del self, presets
            return get(model_cls)

        original_load, ConfigLoader.load = ConfigLoader.load, _mocked_load
        yield
        ConfigLoader.load = original_load
        for config_class, (new, init) in classmethods_map.items():
            config_class.__new__ = new
            config_class.__init__ = init

    def __getitem__(self, config_class: type[ProviderT]) -> ProviderT:
        try:
            return self.get(config_class)
        except ValueError as e:
            raise KeyError(f"{config_class.__name__} not found") from e

    def __setitem__(
        self, config_class: type[ProviderT], factory: Callable[[], ProviderT]
    ):
        self.register(config_class, factory)


def make_custom_method(return_value: Any):
    """
    Create a custom method that returns the given return_value.
    :param return_value: The value to be returned by the custom method.
    :return: A custom method that returns the given return_value."""

    def custom_method(*args, **kwargs):
        return return_value

    return custom_method
