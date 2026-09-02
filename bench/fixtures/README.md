# Canonical benchmark fixtures

This directory contains five deterministic failure scenarios for benchmark and
self-healing-agent tests. Every fixture has the same contract:

- `setup.sh <workdir>` creates the failure state and exits successfully.
- `expected.json` describes the failure, expected outcome, and verification.
- `teardown.sh <workdir>` removes the state created by setup.

The scripts never write outside the work directory supplied by the caller.
The fixture loader is available at `bench/phase-b/orchestrator.py`:

```bash
python3 bench/phase-b/orchestrator.py --list
python3 bench/phase-b/orchestrator.py --fixture dco-signoff --json
```

The fixtures are intentionally small and local-only: no network, credentials,
or external services are required.
