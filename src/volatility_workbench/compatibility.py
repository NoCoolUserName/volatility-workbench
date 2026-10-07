"""Fail before touching case state when the installed shared API is incompatible."""
import importlib

def require_core():
    try:
        api = importlib.import_module('volatility_mcp.api')
    except ImportError as exc:
        raise RuntimeError('Workbench requires volatility-mcp with public API revision 1. Reinstall Workbench from its tested requirements.lock.txt, or install the compatible sibling core checkout in editable mode.') from exc
    if getattr(api, 'API_VERSION', None) != 1:
        raise RuntimeError('Incompatible volatility-mcp API. Workbench requires revision 1. Restore its tested core pin using requirements.lock.txt; do not migrate case data.')
    return api
