"""Reading actions from actions files (textproto)."""

from __future__ import annotations

from google.protobuf import text_format

from run_actions import actions_pb2
from run_actions.action import Action


class ParseError(Exception):
    """An actions file could not be parsed, or is invalid."""


def parse(text: str, path: str = "<string>") -> actions_pb2.ActionList:
    """Parses the textproto content of an actions file.

    path is only used in error messages.
    """
    message = actions_pb2.ActionList()
    try:
        text_format.Parse(text, message)
    except text_format.ParseError as e:
        raise ParseError("%s: %s" % (path, e)) from e
    return message


def to_actions(message: actions_pb2.ActionList, first_id: int, path: str = "<string>") -> list:
    """Converts parsed actions to Actions, with ids starting at first_id."""
    actions = []
    for index in range(len(message.action)):
        declared = message.action[index]
        if declared.name == "":
            raise ParseError("%s: action #%d has no name" % (path, index + 1))
        if declared.script == "":
            raise ParseError("%s: action %r has no script" % (path, declared.name))
        actions.append(
            Action(
                id=first_id + index,
                name=declared.name,
                command=declared.script,
                ignore_error=declared.ignore_error,
            )
        )
    return actions


def load(path: str, first_id: int) -> list:
    """Reads the actions file at path, with ids starting at first_id."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise ParseError("%s: %s" % (path, e)) from e
    return to_actions(parse(text, path), first_id, path)
