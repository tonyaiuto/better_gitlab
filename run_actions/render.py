"""Renders action results as output sections."""

from __future__ import annotations

from typing import BinaryIO

from run_actions import action as action_lib
from run_actions import templates


def order_results(results: list, show_errors_last: bool) -> list:
    """Returns results in display order.

    With show_errors_last, passed results come first, then failed ones; each
    group keeps the original (command line) order.
    """
    if not show_errors_last:
        return list(results)
    passed = []
    failed = []
    for result in results:
        if result.passed():
            passed.append(result)
        else:
            failed.append(result)
    return passed + failed


def _write_line(out: BinaryIO, template_list: list, variables: dict) -> None:
    """Writes the expanded templates, concatenated, as one line."""
    line = ""
    for template in template_list:
        line += template.format_map(variables)
    line += "\n"
    out.write(line.encode("utf-8", errors="replace"))


def render_one(result, out: BinaryIO) -> None:
    variables = action_lib.variables(result)
    _write_line(out, [templates.ACTION_DIVIDER], variables)
    # GitLab expects the section header text on the section_start line.
    _write_line(out, [templates.SECTION_START_HEADER, templates.SECTION_BEGIN], variables)
    # Output bytes are passed through unchanged. We only add a newline when
    # needed so that stderr and SECTION_END each start on their own line.
    out.write(result.stdout)
    if len(result.stdout) > 0 and not result.stdout.endswith(b"\n"):
        out.write(b"\n")
    out.write(result.stderr)
    if len(result.stderr) > 0 and not result.stderr.endswith(b"\n"):
        out.write(b"\n")
    _write_line(out, [templates.SECTION_END], variables)


def render(results: list, show_errors_last: bool, out: BinaryIO) -> None:
    for result in order_results(results, show_errors_last):
        render_one(result, out)
    out.flush()
