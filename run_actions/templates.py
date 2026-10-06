"""Output templates for run_actions.

Each template may contain {VAR} expressions that are filled from the
per-action variables (see action.variables). These are constants for now;
this module is the single place to swap them for a configuration file later.

The section templates follow GitLab's custom collapsible section format:
https://docs.gitlab.com/ci/jobs/job_logs/#custom-collapsible-sections
SECTION_START_HEADER and SECTION_BEGIN are rendered together on one line.
"""

ESC = "\x1b"

ACTION_DIVIDER = "##### {ACTION_NAME}"
SECTION_START_HEADER = "{ESC}[0Ksection_start:{START_TIME}:{SECTION_NAME}[collapsed={PASSED}]\r{ESC}[0K"
SECTION_BEGIN = "{ESC}[36;1mRunning {ACTION_NAME}{ESC}[0;m"
SECTION_END = "{ESC}[0Ksection_end:{END_TIME}:{SECTION_NAME}\r{ESC}[0K"
