"""Runs actions, either all in parallel or one after another."""

from __future__ import annotations

import concurrent.futures
import subprocess
import time

from run_actions.action import Action, ActionResult

# Exit code reported when the action could not be started at all.
SPAWN_FAILURE_EXIT_CODE = 127


def run_one(action: Action) -> ActionResult:
    """Runs a single action with bash, capturing stdout and stderr.

    The environment and working directory are inherited. Never raises for
    a failure to start the process; that is reported as exit code 127.
    """
    start_time = int(time.time())
    try:
        completed = subprocess.run(["bash", "-c", action.command], capture_output=True)
    except OSError as e:
        end_time = int(time.time())
        message = "run_actions: failed to start action: %s\n" % e
        return ActionResult(
            action=action,
            exit_code=SPAWN_FAILURE_EXIT_CODE,
            stdout=b"",
            stderr=message.encode("utf-8", errors="replace"),
            start_time=start_time,
            end_time=end_time,
        )
    end_time = int(time.time())
    return ActionResult(
        action=action,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        start_time=start_time,
        end_time=end_time,
    )


def run_serial(actions: list) -> list:
    """Runs actions one at a time, in order. A failure does not stop the rest."""
    results = []
    for action in actions:
        results.append(run_one(action))
    return results


def run_parallel(actions: list) -> list:
    """Runs all actions at once. Results are returned in the order of actions."""
    if len(actions) == 0:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(actions)) as executor:
        futures = []
        for action in actions:
            futures.append(executor.submit(run_one, action))
        results = []
        for future in futures:
            results.append(future.result())
    return results
