"""Installed application entry point, independent of the current directory."""
from .compatibility import require_core

def main(argv=None):
    try:
        require_core()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None
    from .http import main as run
    return run(argv)
