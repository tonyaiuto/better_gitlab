# presubmit — plan

Last updated: 2026-10-06. Requirements: `/testing_requirements.md`.

## Goal

Given the files changed in a PR, read the `TESTING` files that apply to them and
work out the smallest set of actions and Bazel test runs to execute.

## Decisions

- **Schema:** `presubmit/testing.proto` is the source of truth, so Go or Rust
  ports can reuse it. Files are textproto, parsed with the protobuf Bazel
  module's pure-Python runtime (`py_proto_library`), so nothing is
  pip-installed.
- **Definitions:** `Testing` gains `repeated Action action` and
  `repeated TestSuite test_suite`.
- **Includes bring in everything:** definitions and presubmit blocks.
  - An included file's presubmit blocks apply within the scope of the
    including file's directory.
  - Includes are transitive. Include paths are relative to the repo root.
    A cycle is an error.
- **Names are global** across all loaded files.
  - The same name defined twice with different content is an error; an
    identical repeat is fine.
  - An unknown `check_action` or `check_tests` name is an error.
- **Regexes** use `re.search` against repo-relative paths.
  - A changed file matches if any `include_regex` matches; with no
    `include_regex`, every in-scope file matches.
  - Then any file matching an `exclude_regex` is dropped.
  - If no files are left, the presubmit block is skipped.
- **Scope:** every `TESTING` file in any ancestor directory of a changed file
  applies, not just the nearest one. Its scope is the changed files at or below
  its directory.
- **The file name is a parameter** (default `TESTING`).

## Code layout (`presubmit/`)

| module | role |
|---|---|
| `testing.proto` | `Testing`, `Presubmit`, `Action`, `TestSuite` |
| `source_tree.py` | Interface `SourceTree` (`exists`, `read`); `FsSourceTree`; `MockSourceTree` parsed from a single-file tree spec |
| `changed_files.py` | Interface `ChangedFiles.get() -> list[str]`; `GitDiffChangedFiles(ref)` runs `git diff --name-only <ref>`; `FixedChangedFiles` for tests |
| `discover.py` | changed files → their directories → every ancestor → the `TESTING` files that exist, root first |
| `loader.py` | parse files, resolve includes, build the global definition registry, validate |
| `select.py` | evaluate each presubmit block's regexes against the in-scope files → (action or suite name, files) |
| `plan.py` | aggregation and expansion → `Plan` (a list of actions and a list of test runs) |
| `cli.py` | `main(changed_files_factory)`; prints the plan as JSON, sorted so the output is the same every run |
| `main.py` | default binary: wires in `GitDiffChangedFiles` |

**Swapping in another changed-files source:** a company writes its own
`ChangedFiles` implementation plus a two-line `main.py` that calls
`cli.main(TheirChangedFiles)`, and builds its own `py_binary` around it. The
Datadog version comes later.

### The mock tree format (for tests)

```
/src/main/foo.c
/src/main/TESTING <<<END
presubmit { check_action: "lint" }
END
/src/common/baz.c
```

- Each path line is one file. A path line ending in `<<<TAG` takes the lines
  up to `TAG` as the file's content; other files are empty.
- Leading `/` is stripped, so paths are repo-relative.

## Plan semantics

1. Collect `(action, files)` and `(suite, files)` from every presubmit block
   that has matching files.
2. **Actions:**
   - Make one entry per `machine_type`. With no `machine_type`, use the
     defaults: a constant `DEFAULT_MACHINE_TYPES = ["default"]` for now,
     configurable later.
   - Group by (action name, machine type) and union the file sets.
   - Then expand the command:
     - `{FILES}` becomes the shell-quoted files, sorted, joined with spaces.
     - `{EACH_FILE}` makes one command per file.
     - With neither, the command is used once as written.
3. **Test suites:**
   - Each suite is repeated per `platform`; with no platform, one run with no
     platform.
   - Group by (`test_args`, platform) and union the `tests` patterns.
   - Here, test files only decide whether a suite is selected; they aren't
     passed to the tests.
4. **Output (`Plan`):** each action has a name, machine type, list of commands
   and files; each test run has a platform, test args and patterns. Turning
   this into GitLab jobs or `run_actions` calls is a later step.

## Steps

Each step is a separate commit on branch `presubmit` (worktree
`~/ws/better_github_worktrees/presubmit`): build it, test it, you review it,
then commit.

1. **Bazel and protobuf setup:**
   - add the `protobuf` module dependency
   - add the macOS minimum-version flags to `.bazelrc`
   - write `testing.proto` and a `parse_testing(text)` helper
   - test: parse every field
2. **`source_tree.py`:** the interface, the filesystem version, and the mock
   tree parser. Tests: parsing the format and error cases.
3. **`changed_files.py`:** the interface, the git diff version, and the fixed
   list. Test the git version against a temporary git repo.
4. **`discover.py`:** find the applicable files, root first, and accept a
   different file name. Test with mock trees, including the 5-level
   `foo/bar/baz/ball/bat/foo.c` example.
5. **`loader.py`:** includes (transitive, cycle errors, presubmits scoped to
   the including file), the registry, duplicate and unknown names, missing
   required fields (`name`, `command`).
6. **`select.py`:** include and exclude regexes, the default when no include
   regex is given, scoping, empty blocks skipped.
7. **`plan.py`:** machine types, grouping, `{FILES}` / `{EACH_FILE}`, test
   suite grouping.
8. **`cli.py` and `main.py`:** JSON output. A golden test drives a mock tree,
   a list of changed files and the expected JSON. Also a smoke run against a
   real repo.

Test data for steps 4–8 lives in `presubmit/testdata/*.tree` files, each with
its changed files and expected names, so each case is a single file.

## Status

All 8 steps are done, each in its own commit on branch `presubmit`.

Differences from the plan above:
- `select.py` is `selection.py`, so it can't shadow the standard library's
  `select` module.
- A test suite with no `tests` still produces a test run with no patterns.
- The CLI defaults to `--ref origin/main...HEAD`. `--file PATH` (repeatable)
  skips git and uses the given changed files.
- `cli.main` also takes `add_arguments(parser)`, so a replacement source of
  changed files can add its own flags.

Run it with:
`bazel build //presubmit:presubmit --build_python_zip`, then
`python3 bazel-bin/presubmit/presubmit.zip --repo <checkout> [--ref REF]`.
It prints JSON with `changed_files`, `testing_files`, `actions` and
`test_runs`.

## Not in this phase

- Turning the plan into GitLab jobs and `run_actions` calls.
- The Datadog `ChangedFiles` implementation.
- A checker for `test_args`.
- Whether `METADATA` replaces `TESTING`.
