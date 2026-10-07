# Contributing

Follow AGENTS.md and the ownership map in docs/SEPARATION.md. The core public API
is documented [upstream](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/PUBLIC_API.md).
Do not copy core implementation into this repository. Original source and MIT
attribution are recorded in docs/SEPARATION.md and LICENSE.

Use the sibling editable installation documented in README. Run:

```sh
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python scripts/package_smoke.py
node --check src/volatility_workbench/static/app.js
```

Tests use tiny harmless analyzer fixtures and simulated Codex. Browser checks must
use fixtures or saved data without submitting investigations; record actual checks
and limits in docs/UI_VALIDATION.md. Never track private data or screenshots of cases.
CI installs the pinned core and tests a wheel from outside either source checkout.
