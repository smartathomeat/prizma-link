# Contributing

Thank you for helping improve Prizma Link.

## Before opening a pull request

1. Discuss new protocol or write-control work in an issue without posting customer data,
   unmasked Bluetooth addresses, credentials or raw captures containing identifiers.
2. Keep all new device models read-only by default.
3. A new write command needs independent, repeatable protocol evidence, explicit model gating,
   fail-closed tests and supervised validation on owned or authorised hardware.
4. Do not add code copied or translated from a project whose licence does not clearly permit it.
5. Preserve the existing separation between status detection and write authorisation.

Run the checks before submitting:

```bash
python -m compileall src
ruff check .
mypy src
pytest -q
```

Changes to the Home Assistant app must also keep `addon/bridge` in sync with the root Python
package and pass `tests/test_addon_manifest.py`.

## Scope

Small, reviewable changes are preferred. Documentation, tests and read-only diagnostics are
welcome. Do not include credentials, customer automation, site-specific defaults, compiled
binaries, logs or packet captures in a pull request.
