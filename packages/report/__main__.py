"""``python -m report`` entry point (with ``packages`` on PYTHONPATH)."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
