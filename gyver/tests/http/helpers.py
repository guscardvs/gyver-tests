import asyncio
import typing

from . import typedef

DEFAULT_ENCODING = "utf-8"


def encode_string(string: str, encoding: str = DEFAULT_ENCODING):
    return string.encode(encoding)


def is_stream_like(value: typing.Any):
    return hasattr(value, "read") and asyncio.iscoroutinefunction(value.read)


def wrap_content_stream(content: typing.Union[str, bytes, typedef.StreamLike]):
    if isinstance(content, str):
        content = encode_string(content)

    return typedef.MockStream(content) if isinstance(content, bytes) else content


def build_raw_headers(headers: typing.Mapping[str, str]):
    """Convert a dict of headers to a tuple of tuples.
    Mimics the format of ClientResponse."""
    return tuple(
        (encode_string(key), encode_string(value)) for key, value in headers.items()
    )


def compare_mapping(
    first: typing.Mapping[str, typing.Any],
    second: typing.Mapping[str, typing.Any],
):
    return all(second.get(key) == value for key, value in first.items())
