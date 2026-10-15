"""Restore an explicitly configured administrative alias before opening Workbench."""
from __future__ import annotations

import json
import os
from pathlib import Path


def ensure_relocation_alias() -> bool:
    """Recreate only the missing exact old-root alias; core validates the result."""
    filename = os.environ.get('VOLATILITY_MCP_RELOCATION')
    if not filename:
        return False
    source = Path(filename)
    if not source.is_absolute() or not source.is_file() or source.stat().st_size > 8192:
        raise ValueError('VOLATILITY_MCP_RELOCATION must name a small absolute local file')
    record = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(record, dict) or set(record) != {'logical_root', 'physical_root'}:
        raise ValueError('Relocation file requires exactly logical_root and physical_root')
    old, new = (Path(record[key]) for key in ('logical_root', 'physical_root'))
    if (not old.is_absolute() or not new.is_absolute() or '..' in old.parts or '..' in new.parts
            or old.is_relative_to(new) or new.is_relative_to(old)):
        raise ValueError('Relocation roots must be absolute, distinct, nonoverlapping paths')
    if not new.is_dir() or new.resolve(strict=True) != new:
        raise ValueError('Relocation physical root must be a canonical directory')
    if not old.parent.is_dir() or old.parent.resolve(strict=True) != old.parent:
        raise ValueError('Relocation logical parent must be a canonical directory')

    from volatility_mcp.api import environment
    if old.is_symlink() or old.exists():
        environment()  # Reject a changed alias or occupied old path; never overwrite it.
        return False

    try:
        old.symlink_to(new, target_is_directory=True)
    except FileExistsError:
        environment()  # Another launcher won the race; accept only the exact alias.
        return False
    try:
        environment()  # Apply the core's complete relocation validation.
    except Exception:
        if old.is_symlink() and old.resolve(strict=False) == new:
            old.unlink()
        raise
    return True
