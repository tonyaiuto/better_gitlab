"""Output templates for run_actions.

Each template may contain {VAR} expressions that are filled from the
per-action variables (see action.variables). These are constants for now;
this module is the single place to swap them for a configuration file later.
"""

ESC = "\x1b"

ACTION_DIVIDER = "##### {ACTION_NAME}"
SECTION_START_HEADER = "{ESC}[0Ksection_start:{ACTION_ID}:{ACTION_NAME}[collapsed={PASSED}]"
SECTION_BEGIN = "{ESC}[0K[36;1mRunning {ACTION_NAME}{ESC}[0;m"
SECTION_END = "section_end:{ACTION_ID}:{ACTION_NAME}"
