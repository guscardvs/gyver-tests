import pytest

from .mocker import http_mocker


@pytest.hookimpl
def pytest_runtest_setup(item: pytest.Item):
    if all(mark.name != "mocker" for mark in item.iter_markers()):
        return
    http_mocker.clear()
    http_mocker.activate()


@pytest.hookimpl
def pytest_runtest_teardown(item: pytest.Item):
    if all(mark.name != "mocker" for mark in item.iter_markers()):
        return
    http_mocker.deactivate()
    http_mocker.clear()


def pytest_configure(config: pytest.Config):
    config.addinivalue_line("markers", "mocker: mark tests to activate mocker")
