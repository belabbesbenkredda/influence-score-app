"""Convenience entry point: `python run.py all` from the repo root."""
from psi.run import main
import sys

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
