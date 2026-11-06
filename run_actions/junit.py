"""Writes action results as a JUnit XML report."""

from __future__ import annotations

import datetime
import re
import xml.etree.ElementTree as ET

from run_actions import runner

# ANSI CSI escape sequences, such as color codes and GitLab section markers.
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# Characters that may not appear in an XML 1.0 document.
_XML_ILLEGAL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def clean_text(data: bytes) -> str:
    """Returns captured output as text that is legal in an XML document."""
    text = data.decode("utf-8", errors="replace")
    text = _ANSI_CSI_RE.sub("", text)
    return _XML_ILLEGAL_RE.sub("", text)


def _seconds(value: float) -> str:
    return "%.3f" % value


def _timestamp(unix_time: int) -> str:
    when = datetime.datetime.fromtimestamp(unix_time, tz=datetime.timezone.utc)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_error(result) -> bool:
    return result.exit_code == runner.SPAWN_FAILURE_EXIT_CODE


def _testcase(parent: ET.Element, result, suite_name: str) -> None:
    testcase = ET.SubElement(
        parent,
        "testcase",
        name=result.action.name,
        classname=suite_name,
        time=_seconds(result.duration),
    )
    properties = ET.SubElement(testcase, "properties")
    ET.SubElement(properties, "property", name="action_id", value=str(result.action.id))
    ET.SubElement(properties, "property", name="command", value=clean_text(result.action.command.encode("utf-8")))
    ET.SubElement(properties, "property", name="exit_code", value=str(result.exit_code))
    if not result.passed():
        if _is_error(result):
            ET.SubElement(testcase, "error", message="action could not be started", type="SpawnFailure")
        else:
            ET.SubElement(testcase, "failure", message="exit code %d" % result.exit_code, type="ExitCode")
    stdout = clean_text(result.stdout)
    if len(stdout) > 0:
        ET.SubElement(testcase, "system-out").text = stdout
    stderr = clean_text(result.stderr)
    if len(stderr) > 0:
        ET.SubElement(testcase, "system-err").text = stderr


def build(results: list, wall_time: float, suite_name: str = "run_actions") -> ET.ElementTree:
    """Returns the report for results, in their original (command line) order.

    wall_time is the elapsed time of the whole run, in seconds. It is not
    the sum of the durations, because actions may run in parallel.
    """
    errors = 0
    failures = 0
    for result in results:
        if result.passed():
            continue
        if _is_error(result):
            errors += 1
        else:
            failures += 1
    counts = {
        "tests": str(len(results)),
        "failures": str(failures),
        "errors": str(errors),
        "time": _seconds(wall_time),
    }
    if len(results) > 0:
        counts["timestamp"] = _timestamp(min(result.start_time for result in results))
    testsuites = ET.Element("testsuites", name=suite_name, **counts)
    testsuite = ET.SubElement(testsuites, "testsuite", name=suite_name, skipped="0", **counts)
    for result in results:
        _testcase(testsuite, result, suite_name)
    return ET.ElementTree(testsuites)


def write(results: list, wall_time: float, path: str) -> None:
    tree = build(results, wall_time)
    ET.indent(tree)
    tree.write(path, encoding="utf-8", xml_declaration=True)
