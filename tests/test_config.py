import pytest

from gyver.config.provider import ProviderConfig
from gyver.tests.config.mocker import ConfigMocker
from gyver.tests.config.registry import config_map


class MockConfig(ProviderConfig):
    prefix: str


def test_init():
    mocker = ConfigMocker()
    assert mocker.factories == config_map
    assert mocker._resolved == {}

    custom_factories = ((MockConfig, lambda: MockConfig(prefix="custom")),)
    mocker = ConfigMocker(*custom_factories)
    assert mocker.factories == config_map | dict(custom_factories)
    assert mocker._resolved == {}


def test_resolve():
    config_class = MockConfig
    mocker = ConfigMocker((config_class, lambda: MockConfig(prefix="custom")))
    mocker.resolve(config_class)
    assert config_class in mocker._resolved
    assert isinstance(mocker._resolved[config_class], MockConfig)


def test_resolve_all():
    mocker = ConfigMocker()
    mocker.resolve_all()
    for config_class in mocker.factories:
        assert config_class in mocker._resolved
        assert isinstance(mocker._resolved[config_class], config_class)

    only = [MockConfig]
    mocker = ConfigMocker((MockConfig, lambda: MockConfig(prefix="custom")))
    mocker.resolve_all(only)
    for config_class in only:
        assert config_class in mocker._resolved
        assert isinstance(mocker._resolved[config_class], config_class)
    assert len(mocker._resolved) == len(only)


def test_unresolve():
    mocker = ConfigMocker()
    mocker.resolve_all()
    assert mocker._resolved
    mocker.unresolve()
    assert not mocker._resolved


def test_register():
    mocker = ConfigMocker()
    config_class = MockConfig
    factory = lambda: MockConfig(prefix="custom")
    mocker.register(config_class, factory)
    assert config_class in mocker.factories
    assert mocker.factories[config_class] == factory


def test_get():
    mocker = ConfigMocker()
    config_class = MockConfig
    with pytest.raises(ValueError, match="No factory registered for"):
        mocker.get(config_class)

    factory = lambda: MockConfig(prefix="custom")
    mocker.register(config_class, factory)
    assert isinstance(mocker.get(config_class), MockConfig)
    assert mocker.get(config_class) == mocker._resolved[config_class]


def test_getitem():
    mocker = ConfigMocker()
    config_class = MockConfig
    with pytest.raises(KeyError, match="MockConfig not found"):
        try:
            mocker[config_class]
        except Exception as e:
            print(e)
            raise

    factory = lambda: MockConfig(prefix="custom")
    mocker.register(config_class, factory)
    assert isinstance(mocker[config_class], MockConfig)
    assert mocker[config_class] == mocker._resolved[config_class]


def test_setitem():
    ConfigMocker()
