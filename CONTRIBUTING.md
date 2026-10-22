# Contributing

Original project contributions are accepted under both VSL 1.0 and MIT, as mapped
in [LICENSING.md](LICENSING.md). Preserve upstream notices on third-party material;
do not submit material you cannot license on the applicable terms.

Follow AGENTS.md and the ownership map in docs/SEPARATION.md. The core public API
is documented [upstream](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/PUBLIC_API.md).
Do not copy core implementation into this repository. Original source and MIT
attribution are recorded in docs/SEPARATION.md and LICENSE.

Use the sibling editable installation documented in README. During development,
run the test modules relevant to the change, for example:

```sh
PYTHONPATH=tests .venv/bin/python -m unittest test_generation test_ui -q
```

Before merge/release, run the full suite and installed-wheel smoke once on the
final change. The package smoke command below already runs **all application tests
against fresh installed wheels**; a separate duplicate full local checkout run is
not required. CI retains checkout and installed-wheel checks on supported Python
versions to catch import/package differences. Re-run affected checks after repairs,
not an unchanged suite repeatedly. For a quick full checkout check without a wheel
build, use `.venv/bin/python -m unittest discover -s tests -q`.

Final package and applicable JavaScript checks:

```sh
.venv/bin/python scripts/package_smoke.py
node --check src/volatility_workbench/static/app.js
```

Tests use tiny harmless analyzer fixtures and simulated Codex. Browser checks must
use fixtures or saved data without submitting investigations; record actual checks
and limits in docs/UI_VALIDATION.md. Never track private data or screenshots of cases.
CI installs the pinned core and tests a wheel from outside either source checkout.
Provider contracts can be checked using simulated responses; contributors do not
need subscriptions to every model. Label those checks simulated, and only claim a
real client/provider/model was exercised when it actually was.
