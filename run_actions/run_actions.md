
Goal: A tool that can run several actions and present their results in a "good" way.

- actions are single command lines
- the actions should all run in parallel by default
- there should be an option to have them run serially, in their order on the command line
  - the action on the command line is of the forms
    name='command line with args'
    'command line with args'
  if name= is not used, then the action name is the same as its content
  name => ACTION_NAME
- each action might have stdout and stderr, and an exit code.
- if any action has a non-zero exit code, the entire command should have a fail exit.
  - all the other actions should continue to run, even in serial mode.
  - the variables FAILED and PASSED are set for this action depending on exit code
- every action will have an id # (ACTION_ID) associated with it. For now, lets start with a base of 1000, and add 1 for each action.

The output of this command should be a sequence of output blocks per action. Described below
- by default, we want to emit all the actions that exited cleanly first. Then we want all the actions
  that failed at the end.
  - this is controlled by the bool option "--show_errors_last" which defaults to true.


For an example of the kinds of single line actions we want to run with this command look at
$HOME/ws/datadog-agent/.gitlab/build/lint/technical_linters.yml


## Template names

These can be constants for now. In the future we will read them from a configuration file.
They may contain {var} expressions that get filled from per action variables.

The section templates follow GitLab's custom collapsible section format
(https://docs.gitlab.com/ci/jobs/job_logs/#custom-collapsible-sections).

- ACTION_DIVIDER: default: ##### {ACTION_NAME}
- SECTION_START_HEADER: default: {ESC}[0Ksection_start:{START_TIME}:{SECTION_NAME}[collapsed={PASSED}]\r{ESC}[0K
- SECTION_BEGIN: default: {ESC}[36;1mRunning {ACTION_NAME}{ESC}[0;m
- SECTION_END: default: {ESC}[0Ksection_end:{END_TIME}:{SECTION_NAME}\r{ESC}[0K

## Per action variables

- ACTION_NAME: the action name (the command itself if no name= was given)
- ACTION_ID: 1000 + the action's index on the command line
- SECTION_NAME: ACTION_NAME with every character outside [A-Za-z0-9_.-] replaced
  by "_", followed by "-" and ACTION_ID. Always a legal and unique GitLab section name.
- START_TIME: Unix timestamp (whole seconds) taken just before the action is started
- END_TIME: Unix timestamp (whole seconds) taken just after the action exits
- EXIT_CODE: the action's exit code (127 if it could not be started)
- PASSED / FAILED: "true" or "false", depending on the exit code
- ESC: the escape character (\x1b)

## Per action output

The captured stdout/stderr from each action must be emitted at the end of the process.
Each item below starts on a new line; SECTION_START_HEADER and SECTION_BEGIN share one
line, because GitLab takes the section header text from the section_start line.

- ACTION_DIVIDER
- SECTION_START_HEADER immediately followed by SECTION_BEGIN
- stdout
- stderr
- SECTION_END

stdout and stderr are emitted as raw bytes. If either is non-empty and does not end with
a newline, one is added so that the next item starts on its own line.
