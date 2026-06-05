# Contributing to Exodus

Thanks for helping build an **honest** privacy tool. The bar here is unusual: a privacy tool that overpromises is worse than none, because it produces false confidence. Please internalize the principles below.

## Non-negotiable principles

1. **Honesty over hype.** Never claim protection the code does not deliver. If you cannot defend a claim in `docs/threat-model.md`, it does not go in the README.
2. **Fail closed.** On any uncertainty (classification, local-model outage, parse error), choose the *more private* action — block, do not forward.
3. **The vault never leaves the machine.** No real value in any outbound request, log, or test fixture.
4. **Document notable changes** and keep the README/docs in sync with actual behavior.

## Dev setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,detect]"
pytest
ruff check .
```

## Testing rules

- New privacy behavior must ship with a **canary test** proving no protected value crosses egress (see invariants INV-1..INV-4 in `docs/threat-model.md`).
- Use `respx` to mock the upstream Anthropic API — tests must never hit the network.

## Commit style

- Imperative, English, scoped: `proxy: stream-safe SSE restoration`.
- Reference the milestone when relevant: `(M2)`.

## Architecture discipline

- Respect the layer boundaries in `docs/ESTRUCTURA.md`. The privacy core (`classify`, `policy`, `transform`, `local_model`, `audit`) must not import `proxy/` — it has to stay reusable by the future standalone interface.
