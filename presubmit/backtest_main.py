"""Plans the presubmit jobs for past PRs listed by pr_files.py; see backtest.py."""

import sys
from pathlib import Path

# As in main.py: needed for imports to resolve inside the zipapp.
sys.path.append(str(Path(sys.argv[0]).parent.parent))

from presubmit import backtest

if __name__ == "__main__":
    sys.exit(backtest.main())
