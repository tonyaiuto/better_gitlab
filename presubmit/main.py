"""The presubmit planner, getting changed files from git diff."""

import sys

from presubmit import cli

if __name__ == "__main__":
    sys.exit(cli.main())
