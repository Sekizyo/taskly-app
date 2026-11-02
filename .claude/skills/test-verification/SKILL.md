---
name: test-verification
description: Verify newly written or updated Taskly unit tests – run them focused and then as a full suite, typecheck and format the frontend, check they are deterministic and actually exercise the target code, and fix failures without weakening assertions. Use after writing tests and before reporting.
---

# Test verification

A generated test is only done when it is **green, deterministic, meaningful and clean**.
The CI workflow re-runs everything independently, so anything you skip here will show up
as a failed verification on the PR.

## Steps

1. **Baseline awareness** – if `.test-agent/baseline-status.json` exists, read it. Tests
   that already failed before you started are *not* yours to fix; do not touch them,
   just mention them in the report.
2. **Focused run** – run only the files you created/changed:
   `scripts/agent/run_tests.sh <stack> .test-agent/run <test paths>`.
3. **Fix loop (max 3 attempts per test)** – read the failure carefully and decide:
   - *Test bug* (wrong import, wrong mock shape, wrong expectation about existing
     behaviour) → fix the test.
   - *Source bug* (code contradicts its obvious intent / the PR description) → do NOT
     change the source and do NOT assert the buggy behaviour. Drop that test case and
     record the suspected bug in the report.
   - Never add `skip`, `xfail`, `.skip`, `.only`, `.todo`, retries, or broaden
     assertions (`toBeTruthy()` instead of a value, `except Exception`).
4. **Meaningfulness check** – for each new test, ask: would it fail if the behaviour
   under test broke? Check the coverage JSON written by the run
   (`backend-coverage.json` → `files[...].missing_lines`;
   `frontend-coverage.json` → per-file `lines.pct`) to confirm the changed lines are
   now executed.
5. **Determinism** – run the focused tests a second time. No dependence on wall-clock
   date (use fixed dates or relative comparisons), test order, randomness or network.
6. **Full suite** – run the whole suite of each touched stack (no path args). Everything
   that passed in the baseline must still pass.
7. **Frontend hygiene** – `scripts/agent/run_tests.sh format .test-agent/run <files>` then
   `scripts/agent/run_tests.sh typecheck .test-agent/run`.
8. **Clean up** – no stray files outside the allowed test paths (CI rejects the whole
   patch otherwise). Scratch output belongs in `.test-agent/` only.
