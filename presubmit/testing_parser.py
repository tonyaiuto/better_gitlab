"""Parsing TESTING files (textproto) into Testing messages."""

from __future__ import annotations

from google.protobuf import text_format

from presubmit import testing_pb2


class ParseError(Exception):
    """A TESTING file could not be parsed."""


def parse_testing(text: str, path: str = "<string>") -> testing_pb2.Testing:
    """Parses the textproto content of a TESTING file.

    path is only used in error messages.
    """
    message = testing_pb2.Testing()
    try:
        text_format.Parse(text, message)
    except text_format.ParseError as e:
        raise ParseError("%s: %s" % (path, e)) from e
    return message
