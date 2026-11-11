# Contributing

Thanks for considering contributing to agent-memory-ledger.

## Guiding principles

1. **Fail-closed first.** When in doubt, deny. Never introduce a path that
   fails open.
2. **No new dependencies.** The project is zero-runtime-dependency by design.
3. **Sanitized commits.** No secrets, no personal/organization identifiers,
   no machine paths. Run the CLEAN scan before pushing (see below).
4. **Tests stay green.** Every change must keep the full suite passing.

## Quick start

```bash
pip install -e .
python -m unittest discover -s tests -t . -v
python examples/demo.py
```

## CLEAN scan before any push

Scan the tree for sensitive tokens:

```bash
grep -rniE "secret|token|api[_-]?key" --include=*.py --include=*.md .
```

If you find anything in source/docs/tests, redact it and re-run. Never commit
real credentials, personal names, or organization names.

## Pull requests

- One logical change per PR.
- Add tests for new behavior; regression tests for bug fixes.
- Reference the invariant number (1-8, see README) that your change relates to.