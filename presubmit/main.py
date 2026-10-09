"""The presubmit planner, getting changed files from git diff."""

import sys
from pathlib import Path

# This the py portable app thing seems very broken or I am not
# using it right. This is needed to get imports to resolve.
prog_root = str(Path(sys.argv[0]).parent.parent)
sys.path.append(prog_root)

from presubmit import cli

if __name__ == "__main__":
    sys.exit(cli.main())
