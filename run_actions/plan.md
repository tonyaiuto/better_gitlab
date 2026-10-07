# run_actions — plan and status

Last updated: 2026-10-06

## Goal

A CLI that runs several single-line shell actions (in parallel by default, or
one at a time with `--serial`), captures each one's output, and prints it as
GitLab collapsible sections. Passing actions are printed first and failing ones
last. It exits 1 if any action failed. The spec is in `run_actions.md`.

## Project-wide decisions

- **Python is the reference implementation.** It may later be ported to Go or
  Rust, so the code is plain and explicit and uses only the standard library
  (no pip dependencies).
- **The zip carries its own Python.** The `--build_python_zip` output bundles
  the Bazel Python 3.12 runtime for the platform it was built on (macOS ARM
  here) and runs with that, whatever `python3` launches it. So a zip only runs
  on the platform it was built for: build on Linux for Linux.
- **Bazel builds everything:** Bazel 8.4.2 and rules_python 1.6.3, with
  `.python-version` set to 3.12. Executables are built with:
  `bazel build //run_actions:run_actions --build_python_zip`
- **One git worktree per branch,** under `~/ws/better_github_worktrees/`.
- **Test target:** the datadog-agent checkout at `~/ws/datadog-agent`.

## Design (as built)

| file | role |
|---|---|
| `templates.py` | Output templates. These are constants for now; later they will come from a config file. |
| `action.py` | `Action`, `ActionResult`, `parse_action`, and the per-action variables. |
| `runner.py` | `run_one`, `run_parallel` (a thread pool), `run_serial`. |
| `render.py` | Writes the output sections, passing actions first when asked. |
| `main.py` | The argparse command line. |
| `*_test.py` | `unittest` tests: 4 Bazel test targets, 38 tests. |

- **Action syntax:**
  - `name='command'`, or just `'command'`, in which case the name is the
    command itself.
  - A leading `WORD=` is always read as a name, so `FOO=1 make` runs `1 make`
    as an action named `FOO`. Write `name='FOO=1 make'` to set a variable.
- **IDs:** each action's `ACTION_ID` is 1000 + its position on the command line.
- **Execution:** each action runs as `bash -c <command>` and inherits the
  environment and current directory.
  - One failure never stops the other actions, even with `--serial`.
  - If the command can't be started at all, its exit code is 127.
- **Flags (Bazel style):**
  - `--serial`, `--serial=true|false`, `--noserial`
  - `--show_errors_last` (default true), `--show_errors_last=true|false`,
    `--noshow_errors_last`
  - A value only takes effect in the `=` form: `--show_errors_last false` means
    "true", plus an action named `false`.
  - Everything after `--` is treated as an action.
- **Template variables:** `ACTION_NAME`, `ACTION_ID`, `ESC`, `EXIT_CODE`,
  `PASSED`, `FAILED`, `START_TIME`, `END_TIME`, `SECTION_NAME`.

### Output format: the GitLab standard

This replaces the literal templates first written in the spec.

```
##### {ACTION_NAME}
{ESC}[0Ksection_start:{START_TIME}:{SECTION_NAME}[collapsed={PASSED}]\r{ESC}[0K{ESC}[36;1mRunning {ACTION_NAME}{ESC}[0;m
<stdout>
<stderr>
{ESC}[0Ksection_end:{END_TIME}:{SECTION_NAME}\r{ESC}[0K
```

- `START_TIME` and `END_TIME` are Unix timestamps, so GitLab can show how long
  each section took.
- `SECTION_NAME` is the action name with every character outside
  `[A-Za-z0-9_.-]` replaced by `_`, followed by `-{ACTION_ID}`. This keeps it a
  legal GitLab section name and unique.
- A newline is added before `section_end`, and between stdout and stderr, when
  the output doesn't already end with one.

## Status

- [x] Bazel setup on `main`.
- [x] run_actions built, tested and merged to `main` (`01b5be8`).
- [x] Trial script `examples/datadog_agent/technical_linters.sh`, on branch
      `datadog_lint_test` (`9835a62`; worktree
      `~/ws/better_github_worktrees/datadog_lint_test`). Not merged yet.
- [ ] Run the trial script on a machine that has `dda` and `shellcheck`.

## The datadog-agent trial

The script runs the one-line jobs from
`.gitlab/build/lint/technical_linters.yml` as a single `run_actions` call,
inside a datadog-agent checkout, to test merging those jobs into one GitLab job.

- **Jobs included** (each action is named after its job):
  - `lint_rust_licenses`, `lint_shell_version`, `lint_shell`, `lint_filename`,
    `lint_copyrights`, `lint_docs_links`, `lint_codeowners`, `lint_components`,
    `lint_gopls_plugin`, `lint_python`, `lint_update_go`
  - `validate_modules` and `validate_modules_used_by_otel` (one job with two
    script lines)
- **Jobs left out:**
  - `lint_licenses` and `check_modules_replace` need the `go_deps` and
    `go_tools_deps` downloads.
  - `validate_experiment_systemd_units`, `lint_releasenotes_rst`,
    `lint_releasenotes_unique_ids` and `lint_rtloader` only run when certain
    files change (`rules:`). That depends on selecting actions from changed
    files, which isn't built yet.
- **Running it on another machine:** the zip only runs on the platform it was
  built on, so on a Linux machine build it there (or let the script build it
  from a better_github checkout). Copy the script and `run_actions.zip`
  (from `bazel-bin/run_actions/`), then run:
  `./technical_linters.sh --runner ./run_actions.zip --repo <datadog-agent checkout>`.
  Other flags, such as `--serial`, are passed through to `run_actions`.
- **Result on this Mac:** `dda` and `shellcheck` aren't installed, so none of
  the lint checks actually ran. All 13 actions failed with "command not
  found", were shown as failed sections, and the script exited 1.
- **Watch for:** 11 `dda inv` commands starting at once may conflict with each
  other, for example while `dda` sets up its environment on first use, or over
  shared caches. If the results look odd, compare with a `--serial` run.

## Open issues and follow-ups

- **The zip is about 16 MB and platform-specific.** It bundles Bazel's
  Python 3.12 runtime for the build platform. We need Linux builds for CI
  images, and may want a smaller form.
- **`**` globs:** with bash's `globstar` off, the default and the same as in
  GitLab CI, `**` matches only one directory level. macOS bash 3.2 has no
  `globstar` at all. We keep plain `bash -c` to match CI, and could add a
  `--shell` option or config setting later.
- **Templates** should eventually come from a config file.

## Next parts (not started)

- **`TESTING.pb` action declarations.** These files are spread through the
  source tree, and each one applies to all source under its directory. To pick
  actions, walk up from each changed file to the nearest `TESTING.pb`. No glob
  patterns are involved. Questions to settle:
  - If directories are nested, does a change use only the nearest
    `TESTING.pb`, or every one above it?
  - What happens to a changed file with no `TESTING.pb` above it?
  - Does editing a `TESTING.pb` select its own directory's actions?
- **Selecting actions from the files a PR changes.**
- **Matching actions to runner capabilities** (machine images), and grouping
  actions onto as few or as many runners as needed.
- **Testing requirements:** you're drafting `testing_requirements.md`; not
  started on our side yet.
