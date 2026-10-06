"""Action model: parsing command line arguments into actions, and results."""

from __future__ import annotations

import re
from dataclasses import dataclass

from run_actions import templates

# The first action gets this id; each following action adds 1.
BASE_ACTION_ID = 1000

# name=command. The name must look like an identifier (dots and dashes
# allowed after the first character). DOTALL so commands may span lines.
_NAMED_ACTION_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*)=(.*)$", re.DOTALL)

# Characters not allowed in a GitLab section name.
_SECTION_NAME_ILLEGAL_RE = re.compile(r"[^A-Za-z0-9_.-]")


@dataclass
class Action:
    id: int
    name: str
    command: str


@dataclass
class ActionResult:
    action: Action
    exit_code: int
    stdout: bytes
    stderr: bytes
    # Unix timestamps (whole seconds) taken just before spawn / after exit.
    start_time: int = 0
    end_time: int = 0

    def passed(self) -> bool:
        return self.exit_code == 0


def parse_action(arg: str, id: int) -> Action:
    """Parses 'name=command' or 'command' into an Action.

    Without a name, the name is the command itself. Note that
    'FOO=1 make' parses as name 'FOO' with command '1 make'.
    """
    match = _NAMED_ACTION_RE.match(arg)
    if match is not None:
        return Action(id=id, name=match.group(1), command=match.group(2))
    return Action(id=id, name=arg, command=arg)


def parse_actions(args: list) -> list:
    """Parses all action arguments, assigning ids in command line order."""
    actions = []
    for index in range(len(args)):
        actions.append(parse_action(args[index], BASE_ACTION_ID + index))
    return actions


def bool_str(value: bool) -> str:
    if value:
        return "true"
    return "false"


def section_name(action: Action) -> str:
    """Returns a legal, unique GitLab section name for the action.

    Every character outside [A-Za-z0-9_.-] becomes '_', then '-<ACTION_ID>'
    is appended so that distinct actions never share a section name.
    """
    return _SECTION_NAME_ILLEGAL_RE.sub("_", action.name) + "-" + str(action.id)


def variables(result: ActionResult) -> dict:
    """Returns the template variables for one action result."""
    passed = result.passed()
    return {
        "ACTION_NAME": result.action.name,
        "ACTION_ID": str(result.action.id),
        "SECTION_NAME": section_name(result.action),
        "START_TIME": str(result.start_time),
        "END_TIME": str(result.end_time),
        "ESC": templates.ESC,
        "EXIT_CODE": str(result.exit_code),
        "PASSED": bool_str(passed),
        "FAILED": bool_str(not passed),
    }
