# run_actions

Run several shell commands ("actions"), in parallel by default, then print each
one's stdout and stderr as a GitLab collapsible section. Passing actions are
shown first and collapsed; failing ones are shown last and expanded. The exit
code is 0 only if every action passed.

## Build

```sh
bazel build //run_actions:run_actions
cp -f "$(bazel info bazel-bin)/run_actions/run_actions.pyz" /tmp/run_actions.pyz
```

`run_actions.pyz` is self-contained, so it can be copied anywhere. Run the copy,
not the file in Bazel's output tree, and do not use `bazel run`: actions often
run Bazel themselves, and they could deadlock waiting on the Bazel invocation
that started run_actions. (`cp -f` is needed because Bazel's outputs are
read-only.)

## Actions on the command line

Each argument is an action, written as `name='command'`, or just `'command'`, in
which case the command is also its name.

```sh
/tmp/run_actions.pyz \
    aaa='echo aaa' \
    bbb='echo bbb >&2; exit 1' \
    'echo ccc'
echo "exit code: $?"
```

`bbb` fails, so it is shown last and run_actions exits 1.

## Actions in a file

Actions can also be declared in a textproto file (schema:
[actions.proto](actions.proto)). Each action has a `name` and a `script`, which
is run with `bash -c`. With `ignore_error: true`, the action is still run and
reported as failed, but its failure does not make run_actions fail.

```sh
cat > my_actions.textproto <<'EOF'
action {
  name: "aaa"
  script: "echo aaa"
}
action {
  name: "bbb"
  script: "echo bbb\n"
          "echo more bbb"
}
action {
  name: "allowed_to_fail"
  script: "echo trying; exit 1"
  ignore_error: true
}
EOF

/tmp/run_actions.pyz --actions_file=my_actions.textproto
echo "exit code: $?"
```

This exits 0: the only failure is `allowed_to_fail`.

Files and command line actions can be mixed, and `--actions_file` may be given
more than once. Actions from files come first, in flag order. Action names must
be unique.

```sh
/tmp/run_actions.pyz \
    --actions_file=my_actions.textproto ccc='echo ccc'
```

## JUnit report

`--junit_xml=PATH` also writes a JUnit XML report, with one testcase per action:
its duration, exit code, stdout and stderr.

```sh
/tmp/run_actions.pyz \
    --junit_xml=junit.xml \
    --actions_file=my_actions.textproto
cat junit.xml
```

## Other options

- `--serial`: run actions one at a time, in order, instead of in parallel. A
  failure does not stop the rest.
- `--noshow_errors_last`: show actions in their given order, not failures last.
- `--help`: all options.

See [run_actions.md](run_actions.md) for the full specification of the output
format.
