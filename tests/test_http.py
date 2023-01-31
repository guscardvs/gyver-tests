import asyncio
import json

import pytest
from aiohttp import ClientSession

from gyver.tests.http import http_mocker
from gyver.tests.http.exc import NoUrlMatching


class DummyAsyncStream(asyncio.StreamReader):
    def __init__(self, data):
        super().__init__()
        self.size = len(data)
        self.feed_data(data)
        self.feed_eof()


async def test_fake_request():
    desired_response = b"example data"
    url = "http://example.com/"

    http_mocker.register_uri("GET", url, body=desired_response)

    response = await http_mocker.fake_request("GET", url)
    data = await response.read()
    assert data == desired_response


def test_register_uri():
    url = "http://example.com/"
    desired_response = b"example data"

    http_mocker.register_uri("GET", url, body=desired_response)
    options = http_mocker.registry[("GET", "http://example.com/")]
    assert options == {"body": b"example data"}


def test_register_json_uri():
    url = "http://example.com/"
    desired_response = {"test_key": "test_value"}

    http_mocker.register_json_uri("GET", url, body=desired_response)
    options = http_mocker.registry[("GET", "http://example.com/")]
    assert isinstance(options, dict)
    assert json.loads(options.get("body").decode("utf-8")) == desired_response


async def test_param_handling():
    url = "http://example-params.com/?test=test"
    desired_error_msg = (
        "No URLs matching GET http://example-params.com/?test=test"
        " with params {'test': ('test',)}. "
        "Request failed."
    )
    with pytest.raises(NoUrlMatching) as exc_info:
        await http_mocker.fake_request("GET", url)
    assert str(exc_info.value) == desired_error_msg


async def test_params():
    desired_response = b"example data"
    url = "http://example.com/"
    params = {"meow": "quack", "woof": "beans"}

    http_mocker.register_uri("GET", url, params=params, body=desired_response)

    response = await http_mocker.fake_request(
        "GET", "http://example.com/?meow=quack&woof=beans"
    )
    data = await response.read()
    assert data == desired_response


async def test_str_response_encoding():
    http_mocker.register_uri("GET", "http://example.com/", body="example résumé data")
    response = await http_mocker.fake_request("GET", "http://example.com/")
    data = await response.read()
    assert data == "example résumé data".encode("utf-8")


@pytest.mark.mocker
async def test_has_call():
    http_mocker.register_uri(
        "GET",
        "http://example.com/",
        params={"alpha": "1", "beta": ""},
        body="foo",
    )
    response = await http_mocker.fake_request(
        "GET", "http://example.com/?alpha=1&beta="
    )
    assert await response.read() == b"foo"

    params_equivalent = [
        "http://example.com/?alpha=1&beta=",
        "http://example.com/?beta=&alpha=1",
    ]
    for uri in params_equivalent:
        assert http_mocker.has_call(method="GET", uri=uri)

    different_params = [
        "http://example.com/",
        "http://example.com/?alpha=2&beta=",
        # 'http://example.com/?alpha=1',  # buggy atm
        "http://example.com/?beta=",
        "http://example.com/?alpha=1&beta=1",
        "http://example.com/?alpha=&beta=",
    ]
    for uri in different_params:
        assert not http_mocker.has_call(method="GET", uri=uri)

    assert http_mocker.has_call(
        method="GET",
        uri="http://example.com/",
        params={"alpha": "1", "beta": ""},
    )
    assert http_mocker.has_call(
        method="GET", uri="http://example.com/", check_params=False
    )
    assert not http_mocker.has_call(
        method="POST", uri="http://example.com/?alpha=1&beta="
    )
    assert not http_mocker.has_call(method="GET", uri="http://otherexample.com/")


def test_activate():  # sourcery skip: extract-duplicate-method
    orig_real_id = id(ClientSession._request)
    orig_fake_id = id(http_mocker.fake_request)

    assert http_mocker.request is None
    assert ClientSession._request != http_mocker.fake_request
    assert id(ClientSession._request) == orig_real_id
    assert id(ClientSession._request) != orig_fake_id

    http_mocker.activate()

    assert http_mocker.request is not None
    assert id(http_mocker.request) == orig_real_id

    assert ClientSession._request == http_mocker.fake_request
    assert id(ClientSession._request) != orig_real_id
    assert id(ClientSession._request) == orig_fake_id

    http_mocker.deactivate()

    assert http_mocker.request is None
    assert ClientSession._request != http_mocker.fake_request
    assert id(ClientSession._request) == orig_real_id
    assert id(ClientSession._request) != orig_fake_id


async def test_multiple_responses():
    http_mocker.register_uri(
        "GET",
        "http://example.com/",
        responses=[
            {
                "status": 200,
                "body": "moo",
            },
            {
                "status": 200,
                "body": "quack",
            },
        ],
    )

    first_resp = await http_mocker.fake_request("GET", "http://example.com/")
    assert await first_resp.read() == b"moo"

    second_resp = await http_mocker.fake_request("GET", "http://example.com/")
    assert await second_resp.read() == b"quack"

    with pytest.raises(Exception):
        await http_mocker.fake_request("GET", "http://example.com/")


def test_no_params_in_responses():
    with pytest.raises(ValueError):
        http_mocker.register_uri(
            "GET",
            "http://example.com/",
            responses=[
                {
                    "status": 200,
                    "body": "moo",
                    "params": {"alpha": "1", "beta": ""},
                },
            ],
        )

    with pytest.raises(ValueError):
        http_mocker.register_uri(
            "GET",
            "http://example.com/",
            responses=[
                {
                    "status": 200,
                    "body": "woof",
                },
                {
                    "status": 200,
                    "body": "moo",
                    "params": {"alpha": "1", "beta": ""},
                },
            ],
        )


async def test_headers_in_response():
    http_mocker.register_uri(
        "GET", "http://example.com/", headers={"X-Magic-Header": "1"}
    )

    first_resp = await http_mocker.fake_request("GET", "http://example.com/")
    assert "X-Magic-Header" in first_resp.headers


async def test_async_streaming_body():
    stream = DummyAsyncStream(b"meow")
    http_mocker.register_uri("GET", "http://example.com/", body=stream)

    resp = await http_mocker.fake_request("GET", "http://example.com/")
    assert await resp.read() == b"meow"


async def test_invalid_body():
    with pytest.raises(TypeError):
        http_mocker.register_uri("GET", "http://example.com/", body=1234)


async def test_passed_data_is_read():
    http_mocker.register_uri("GET", "http://example.com/", body="woof")

    stream = DummyAsyncStream(b"meow")
    assert not stream.at_eof()

    resp = await http_mocker.fake_request("GET", "http://example.com/", data=stream)

    assert stream.at_eof()
    assert await resp.read() == b"woof"


async def test_aiohttp_request():
    http_mocker.register_uri("GET", "http://example.com/", body=b"example data")

    http_mocker.activate()
    async with ClientSession() as session:
        async with session.get("http://example.com/") as response:
            assert await response.read() == b"example data"
    http_mocker.deactivate()
