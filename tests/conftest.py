import sys
import pathlib

# ensure project root is on sys.path so tests can import project modules if needed
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
