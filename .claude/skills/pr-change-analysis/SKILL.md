---
name: pr-change-analysis
description: Decide which changed source files in a Taskly pull request (or backfill request) need new or updated unit tests, which existing tests they map to, and which to skip with a reason. Use before writing any test for a diff.
---

# PR change analysis

Goal: turn a diff into a short, justified test plan. Decide *per changed source file*:
**create**, **update** or **skip**.

## Inputs

- `.test-agent/changes.json` (CI) – produced deterministically by
  `scripts/agent/changed_files.py`. It already lists in-scope files per stack with
  `existing_tests` and a `suggested_test` path, plus files skipped by rule. Do not
  widen the scope beyond the files listed there.
- The diff itself: `git diff <base>...HEAD -- <path>` (base SHA is given in the prompt).
  Locally, without CI, run `python3 scripts/agent/changed_files.py --base origin/main`.

## Procedure

For each in-scope file:

1. Read the diff hunk **and** the full current file. Identify the changed *behaviour*:
   new/changed functions, branches, error paths, props, request/response shapes.
2. Read the existing tests for it (`existing_tests`), and grep for other tests that
   exercise the symbol (`Grep` for the function/component name under the test dirs).
3. Decide:
   - **create** – new behaviour with no test exercising it.
   - **update** – the change intentionally alters behaviour an existing test asserts
     (renamed field, new required param, changed message), or an existing test file
     for the module is the natural home for new cases. Prefer adding cases to the
     existing file over creating a parallel one.
   - **skip** – the change has no behaviour to test (rename, formatting, comment, type
     only, pure re-export, style tokens), behaviour is already covered by existing
     tests (say which), or testing would require an integration environment (real
     Postgres, real network) – say so explicitly.
4. Note risks the PR introduces that tests cannot cover (e.g. migrations, bugs you
   spotted) – they go into the report summary.

## Mapping conventions

| Source | Test location |
|---|---|
| `backend/app/<path>/<mod>.py` | `backend/tests/<path>/test_<mod>.py` (add `__init__.py` in new test dirs) |
| `frontend/src/<path>/<Name>.tsx` | `frontend/src/<path>/<Name>.test.tsx` (colocated) |
| `frontend/src/<path>/<name>.ts` | `frontend/src/<path>/<name>.test.ts` (`.tsx` if the test needs JSX, e.g. a provider wrapper) |

## What makes a test worth writing

Prioritise, in order: error handling and edge cases on changed branches → public
contract (HTTP status/body, component output for given props, hook return values) →
interactions (callbacks, cache updates). Avoid: snapshot tests, asserting on
implementation details (private state, CSS classes), re-testing libraries
(FastAPI/Pydantic validation itself, React Query internals).
