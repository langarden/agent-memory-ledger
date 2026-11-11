# Security

## Reporting a vulnerability

Please report vulnerabilities privately to the maintainers at
`2307788504@qq.com`. Do not open a public issue for security problems.

## Design posture

**Fail-closed.** The engine assumes the worst about callers and data:

- unknown role / unknown layer -> deny
- subagent writing core -> deny
- direct core promote without master -> deny
- tampered hash chain -> `verify()` returns `False` loudly
- expired recycle entries -> purged only after full retention

## Status

This is a **research prototype / reference implementation**, not a hardened
production product. It demonstrates a verifiable memory architecture and its
invariants. Review the code before relying on it in production. The project
intentionally does not persist secrets: payloads are sanitized or stored as
hashes (see `aml/security.py`).

## Responsible disclosure

- Do not test on third-party systems.
- Do not include real secrets in any issue or commit.
- Include a minimal repro (code + commands) when possible.