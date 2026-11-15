"""Run pr-brief on a local diff file without any network access.

Example: python scripts/run_local.py --diff tests/fixtures/diffs/medium.patch --provider mock
"""

import sys

from pr_brief.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
