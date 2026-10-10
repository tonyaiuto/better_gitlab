"""The presubmit planner, getting changed files from git diff."""

import sys
from pathlib import Path

# This the py portable app thing seems very broken or I am not
# using it right. This is needed to get imports to resolve.
sys.path.append(str(Path(sys.argv[0]).parent.parent))

from presubmit import cli

if __name__ == "__main__":
    sys.exit(cli.main())
