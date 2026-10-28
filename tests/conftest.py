import sys
from pathlib import Path

# Make the repo root importable so tests can use packages.* imports.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
