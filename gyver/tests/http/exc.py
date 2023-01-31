from gyver.exc import GyverError


class HTTPMockError(GyverError):
    """Base class for all AioHttPrettyErrors"""


class NoUrlMatching(HTTPMockError, KeyError):
    """No url matches received url with given params and method"""

    def __str__(self) -> str:
        return Exception.__str__(self)


class ExhaustedAllResponses(HTTPMockError, IndexError):
    """No response left for given url"""


class InvalidBody(HTTPMockError, TypeError):
    """Received invalid body type"""


class InvalidResponses(HTTPMockError, ValueError):
    """Cannot specify params in responses"""
