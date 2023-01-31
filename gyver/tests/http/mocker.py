import asyncio
import copy
import json
import typing
from contextlib import contextmanager
from functools import wraps
from http import HTTPStatus
from unittest.mock import Mock

from aiohttp import ClientSession
from aiohttp.client import ClientResponse
from aiohttp.helpers import TimerNoop
from multidict import CIMultiDict, CIMultiDictProxy

from . import exc, helpers, typedef

METHODS = typing.Literal[
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "HEAD",
    "OPTIONS",
    "DELETE",
]
AsyncCallableT = typing.TypeVar(
    "AsyncCallableT", bound=typing.Callable[..., typing.Coroutine]
)
CallableT = typing.TypeVar("CallableT", bound=typing.Callable)


class Mocker:
    def __init__(self):
        self.calls: typing.List[typing.MutableMapping[str, typing.Any]] = []
        self.registry: dict[
            tuple[str, typedef.FrozenURL], typedef.ResponseInRegistry
        ] = {}
        self.request = None

    async def fake_request(
        self, method: METHODS, uri: str, **kwargs: typing.Any
    ):

        response = self._find_request(method, uri, kwargs)

        await self.process_request(**kwargs)
        self.make_call(
            method=method,
            uri=uri,
            **kwargs,
        )

        return self._build_response(method, uri, response)

    async def process_request(self, **kwargs):
        """Process request options as if the request was actually executed."""
        data = kwargs.get("data")
        if isinstance(data, asyncio.StreamReader):
            await data.read()

    def make_call(self, *, method: METHODS, uri: str, **kwargs):
        self.calls.append(
            {
                "method": method,
                "uri": typedef.FrozenURL(
                    uri, params=kwargs.pop("params", None)
                ),
                **kwargs,
            }
        )

    def _find_request(
        self,
        method: METHODS,
        uri: str,
        kwargs: typing.Mapping[str, typing.Any],
    ):
        params = kwargs.get("params")
        url = typedef.FrozenURL(uri, params=params)

        try:
            response = self.registry[(method, url)]
        except KeyError as error:
            raise exc.NoUrlMatching(
                "No URLs matching {method} {uri} with params {url.params}. "
                "Request failed.".format(method=method, uri=uri, url=url)
            ) from error

        if isinstance(response, typing.MutableSequence):
            try:
                response = response.pop(0)
            except IndexError as error:
                raise exc.ExhaustedAllResponses(
                    "No responses left."
                ) from error

        return response

    def _build_response(
        self,
        method: METHODS,
        uri: str,
        response: typing.Mapping[str, typing.Any],
    ):
        loop = Mock()
        loop.get_debug = Mock()
        loop.get_debug.return_value = True
        # When init `ClientResponse`, the second parameter must
        # be of type `yarl.URL`
        # TODO: Integrate a property of this type to `ImmutableFurl`
        url = typedef.FrozenURL(uri)
        mock_response = ClientResponse(
            method,
            url.as_yarl,
            request_info=Mock(),
            writer=Mock(),
            continue100=None,
            timer=TimerNoop(),
            traces=[],
            loop=loop,
            session=Mock(),
        )

        content = helpers.wrap_content_stream(
            response.get("body", "gyver-mock")
        )
        mock_response.content = content  # type: ignore

        # Build response headers manually
        headers = CIMultiDict(response.get("headers", {}))
        if response.get("auto_length"):
            # Calculate and overwrite the "Content-Length" header on-the-fly
            # if Waterbutler tests
            # call `aiohttpretty.register_uri()` with `auto_length=True`
            headers.update({"Content-Length": str(content)})
        raw_headers = helpers.build_raw_headers(headers)

        mock_response._headers = CIMultiDictProxy(headers)
        mock_response._raw_headers = raw_headers

        # Set response status and reason
        mock_response.status = response.get("status", HTTPStatus.OK)
        mock_response.reason = response.get("reason", "")
        return mock_response

    def _validate_body(self, options: typing.Mapping[str, typing.Any]):
        """Validate body type to prevent unexpected behavior"""
        if body := options.get("body"):
            if not isinstance(
                body, (str, bytes)
            ) and not helpers.is_stream_like(body):
                raise exc.InvalidBody(body)
        if responses := options.get("responses"):
            for response in responses:
                self._validate_body(response)

    def register_uri(self, method: METHODS, uri: str, **options: typing.Any):
        if any(x.get("params") for x in options.get("responses", [])):
            raise exc.InvalidResponses(
                "Cannot specify params in responses, "
                "call register multiple times."
            )
        self._validate_body(options)
        url = typedef.FrozenURL(uri, params=options.pop("params", {}))
        self.registry[(method, url)] = options.get("responses", options)

    def register_json_uri(
        self,
        method: METHODS,
        uri: str,
        body: typing.Optional[typing.Any] = None,
        headers: typing.Optional[typing.Mapping[str, str]] = None,
        params: typing.Optional[typing.Mapping[str, str]] = None,
        **options: typing.Any,
    ):
        body = helpers.encode_string(json.dumps(body))
        headers = {
            "Content-Type": "application/json",
            **(headers or {}),
        }
        self.register_uri(
            method,
            uri,
            body=body,
            headers=headers,
            params=params or {},
            **options,
        )

    def activate(self):
        ClientSession._request, self.request = (  # type: ignore
            self.fake_request,
            ClientSession._request,
        )

    def deactivate(self):
        (ClientSession._request, self.request) = (  # type: ignore
            self.request,
            None,
        )

    def clear(self):
        self.calls = []
        self.registry = {}

    def has_call(self, uri: str, check_params: bool = True, **kwargs):
        """Check to see if the given uri was called.  By default will verify
        that the query params
        match up.  Setting ``check_params`` to `False` will strip params from
        the *called* uri, not
        the passed-in uri."""
        kwargs["uri"] = typedef.FrozenURL(
            uri, params=kwargs.pop("params", None)
        )
        for call in self.calls:
            if not check_params:
                call = copy.deepcopy(call)
                call["uri"] = call["uri"].with_out_params()
            if helpers.compare_mapping(kwargs, call):
                return True
        return False

    @contextmanager
    def open(self, clear: bool = True):
        if clear:
            self.clear()
        self.activate()
        yield
        self.deactivate()

    def async_decorate(self, func: AsyncCallableT) -> AsyncCallableT:
        @wraps(func)
        async def inner(*args, **kwargs):
            with self.open():
                return await func(*args, **kwargs)

        return inner  # type: ignore

    def decorate(self, func: CallableT) -> CallableT:
        return self.open()(func)  # type: ignore


http_mocker = Mocker()
