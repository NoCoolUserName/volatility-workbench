"""Installed application entry point, independent of the current directory."""
import sys
from .compatibility import require_core
from .launcher import ensure_relocation_alias

def main(argv=None):
    try:
        require_core()
        arguments = sys.argv[1:] if argv is None else argv
        repaired = False if '-h' in arguments or '--help' in arguments else ensure_relocation_alias()
    except (RuntimeError, ValueError, OSError) as exc:
        raise SystemExit(f"Workbench startup failed: {exc}") from None
    if repaired:
        print("Restored the configured historical Forensics path for saved case references.")
    from .http import main as run
    return run(argv)
