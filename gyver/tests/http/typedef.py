import typing
from unittest.mock import Mock

import yarl
from aiohttp.base_protocol import BaseProtocol
from aiohttp.streams import StreamReader
from gyver.url import URL, Query


class FrozenURL:
    def __init__(
        self,
        url: str,
        params: typing.Optional[typing.Mapping[str, str]] = None,
    ) -> None:
        self._str_url = url
        self._url = URL(url)
        self._params = self._url.query.add(params).params
        self._url.query = Query("")

    def with_out_params(self):
        return FrozenURL(self.url)

    @property
    def url(self):
        return self._url.encode()

    @property
    def params(self):
        return {key: tuple(value) for key, value in self._params.items()}

    @property
    def as_yarl(self):
        return yarl.URL(self.url)

    def __eq__(self, other) -> bool:
        return hash(self) == hash(other)

    def __hash__(self) -> int:
        return hash(
            self.url
            + "".join(
                arg if self.params[x] and (arg := self.params[x][0]) else ""
                for x in sorted(self.params)
            )
        )


DEFAULT_LIMIT = 2**16


class MockStream(StreamReader):
    def __init__(self, data: typing.Any, limit: int = DEFAULT_LIMIT):
        protocol = BaseProtocol(Mock())
        super().__init__(protocol, limit)
        self.size = len(data)
        self.feed_data(data)
        self.feed_eof()


class StreamLike(typing.Protocol):
    async def read(self, n: int) -> bytes:
        ...

    @property
    def size(self) -> int:
        ...


OptionalMapping = typing.Optional[typing.Mapping[str, str]]
BodyType = typing.Union[str, bytes, StreamLike, None]


class ResponseType(typing.TypedDict, total=False):
    status: int
    reason: str
    auto_length: bool
    headers: typing.Mapping[str, str]
    body: typing.Mapping[str, str]


class _ResponseInRegistry(typing.TypedDict, total=False):
    body: typing.Any
    headers: OptionalMapping
    params: OptionalMapping
    responses: typing.Optional[list[ResponseType]]
    status: int
    reason: str
    auto_length: bool


ResponseInRegistry = typing.Union[_ResponseInRegistry, list[ResponseType]]
