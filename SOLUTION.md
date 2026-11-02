# Solution – unit-test agent and agentic PR workflow

A Claude Code **custom agent** (`test-engineer`) with five **reusable skills** writes and
updates unit tests for the FastAPI backend (pytest) and the React/TypeScript frontend
(Vitest + Testing Library). A GitHub Actions **agentic workflow** runs it on every pull
request, verifies its output independently, commits the verified tests to the PR branch
and reports everything in a single PR comment.

## Results of the test backfill

| | Before | After |
|---|---|---|
| Backend (pytest) | 21 tests · 42 % coverage (stmt + branch) | **58 tests · 100 %** |
| Frontend (Vitest) | 18 tests · 46 % statements / 44 % branches | **99 tests · 99.4 % / 97.8 %** |
| Agent tooling (pytest) | – | 37 tests (guard, scoping, report rendering) |

No application code was changed. All suites are deterministic (repeated runs), the
frontend type-checks and passes `prettier --check`.

## Where things live

| Path | What |
|---|---|
| `.claude/agents/test-engineer.md` | Custom agent: role, hard rules, workflow, preloaded skills |
| `.claude/skills/pr-change-analysis/` | Diff → per-file decision: *create / update / skip* + reason |
| `.claude/skills/python-unit-tests/` | Backend conventions, fixtures, patterns per layer, run commands |
| `.claude/skills/react-unit-tests/` | Frontend conventions, design-system mocks, React Query / fetch patterns |
| `.claude/skills/test-verification/` | Run → fix loop (max 3), no weakening, determinism, full suite, hygiene |
| `.claude/skills/test-report/` | Structured `.test-agent/report.json` schema |
| `.claude/settings.json` | Shared, permissive-but-safe project permissions (local use) |
| `.github/test-agent/settings.json` | **CI-only** locked-down policy (`dontAsk`, test-path-only edits) |
| `.github/test-agent/prompt.md` | Run prompt (no PR title/body is ever injected) |
| `.github/workflows/test-agent.yml` | Agentic PR workflow |
| `.github/workflows/ci.yml` | Regular CI: both suites, typecheck, formatting, tooling tests |
| `scripts/agent/` | Deterministic helpers shared by agent and CI (see below) |

**How they are used at runtime.** The workflow starts `claude -p … --agent test-engineer`.
The agent definition preloads the five skills; the agent applies `pr-change-analysis`
first, then the matching stack skill per file, then `test-verification`, and ends with
`test-report`. Locally the same agent is used for backfilling:
`claude --agent test-engineer "Add missing tests for backend/app/core"` (or ask for the
*test-engineer* agent in an interactive session).

## The PR workflow

```
scope ─────────► generate ─────────────► verify ──────────────► publish
contents:read    contents:read           contents:read          contents:write
                 + ANTHROPIC_API_KEY     no secrets             pull-requests:write
deterministic    agent run → patch +     guard → apply →        commit verified patch,
file scoping     report artifact         re-run everything      sticky PR comment
```

1. **scope** – `changed_files.py` classifies the diff. Declarations, schemas, types,
   styles, stories, barrels, entrypoints and deleted files are skipped by rule; the rest
   is mapped to existing/suggested test files (max 20 files). No testable change → the
   agent is **not run** (no cost) and the comment says so.
2. **generate** – installs deps (`npm ci --ignore-scripts`), records a **baseline** run
   (so pre-existing failures aren't blamed on, or "fixed" by, the agent), runs the agent
   with a budget cap, then exports a `git diff` patch and the agent's report.
3. **verify** – `guard_paths.py` validates the patch; it is applied to a clean checkout
   and **all suites are re-run independently** (the agent's self-report is never used as
   a result), the agent's test files are run twice more to catch flakiness, the frontend
   is type-checked and format-checked.
4. **publish** – only if verification is fully green: re-guards, `git apply`, commits as
   `github-actions[bot]` with a `Test-Agent: true` trailer and pushes to the PR branch.
   Always upserts one comment (scope, per-file decisions, skills used, files changed,
   before/after test results, total and per-file coverage, checks, cost/turns) and writes
   it to the job summary. The check fails for `rejected`, `verification-failed` and
   `agent-failed` outcomes.

Controls: label `skip-test-agent` opts a PR out; label `run-test-agent` re-runs it.

### Prerequisites

- Repository secret **`ANTHROPIC_API_KEY`**.
- *Settings → Actions → General → Workflow permissions*: **Read and write**, so the
  `publish` job can push and comment (job-level `permissions:` keep every other job
  read-only). Branch protection must allow `github-actions[bot]` to push to PR branches.
- Optional repository variables: `TEST_AGENT_MODEL` (default `claude-sonnet-5-5`),
  `TEST_AGENT_MAX_BUDGET_USD` (default `5`).
- Labels `skip-test-agent` and `run-test-agent` (optional).

## Main technical decisions

| Decision | Rationale |
|---|---|
| **Claude Code** with project agents/skills | Agents and skills are plain Markdown in the repo – versioned, reviewable, usable both locally and in CI with the same definitions. Pinned CLI version (2.1.316). |
| **Deterministic shell around a non-deterministic core** | Scoping, path policy, test execution, coverage and reporting are scripts with tests; the LLM only decides *what to test and how*. Results are reproducible and auditable. |
| **Generate → verify → publish split** | Separates the secret (API key), untrusted code execution (tests) and the write token into different jobs. The write job never executes PR code. |
| **Patch + guard instead of letting the agent commit** | The agent has no git write or GitHub access. A strict allowlist (`backend/tests/**/*.py` except `conftest.py`, `frontend/src/**/*.test.ts(x)`; no deletions, renames, mode changes, symlinks, binaries, oversized patches) is the hard boundary, independent of the prompt. |
| **Commit to the PR branch** | Tests land where reviewers already look; one sticky comment explains every decision. Commits by `GITHUB_TOKEN` don't re-trigger workflows, which prevents agent loops (the trailer check is a second guard). |
| **Agent tooling taken from the base branch** | `.claude/`, `scripts/agent/` and `.github/test-agent/` are restored from the base commit, so a PR cannot change the rules it is evaluated with. |
| **Shared `run_tests.sh`** | The agent, CI and the workflow use one entry point producing JUnit + coverage JSON, so "green for the agent" means "green in CI". |

### Security summary

- Fork PRs are skipped (no secrets, no write token); only same-repository PRs run.
- `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` strips credentials from processes the agent starts
  (pytest/vitest run untrusted code). No GitHub token exists in the agent job
  (`persist-credentials: false`, `contents: read`).
- CI policy: `dontAsk` mode – anything not allowlisted is denied; Bash limited to
  `run_tests.sh`, the scoping script and read-only git; no web tools; `.env` reads denied.
- Repository content (code, comments, commits, test output) is declared data, not
  instructions; PR title/body are never put in the prompt. Agent text in the comment is
  escaped (HTML, tables, `@`-mentions) and schema-validated.
- All actions pinned by commit SHA; `permissions: {}` at workflow level, granted per job;
  untrusted values passed via `env`, never interpolated into scripts; `actionlint` clean.

## Example run

**Backfill (this repository).** The backfill was done interactively with Claude Code
following the same skills in order (analysis → stack skill → verification) – before the
agent definition was registered in that session, so it was not a literal
`--agent test-engineer` run. Example decision: for
`backend/app/core/config.py` (0 % → 100 %) the decision was *create*
`tests/core/test_config.py` covering explicit-URL precedence, `DATABASE_URL`, URL building
with password escaping, a missing variable, and `.env` loading without override, with
`load_dotenv` patched so a developer's `.env` can never leak into the test. During
verification, two first drafts failed and were fixed rather than loosened: an assertion on
FastAPI's internal route table (replaced by the public OpenAPI schema) and an identity
check on `sessionmaker.class_` (replaced by `issubclass`).

**Pipeline dry run (local, without the LLM).** Verified with throwaway clones: base-branch
tooling replaces a PR's edits to `.claude/`; agent edits to tooling paths are excluded from
the patch; a test-only patch is allowed and applies to a fresh checkout; a patch that also
touches `backend/app/factory.py` is rejected as a whole. `render_report.py` output for real
before/after artifacts:

| Stack | Before agent | After agent | Coverage before → after |
|---|---|---|---|
| backend | ✅ 21/21 passed | ✅ 58/58 passed | 42.4% → 100.0% (+57.6) |
| frontend | ✅ 18/18 passed | ✅ 99/99 passed | 47.7% → 100.0% (+52.3) |

**Demo pull request.** <!-- TODO: replace with the PR link and a copy of the agent comment once the workflow has run. -->
Feature *task statistics* (no tests included): `GET /api/todos/stats` (repository
aggregate + route) and a `TodoStats` summary line on the tasks page. Expected agent work:
*create* tests for `TodoRepository.stats` and the `/stats` route, **update** the existing
`tests/test_factory.py` (it asserts the exact API surface and fails on the new route),
*create* `TodoStats.test.tsx` and extend `utils/todos.test.ts` for `summarizeTodos`, and
*skip* `schemas.py` (declarative). The real decisions, skills used and test results are in
the PR comment: _link to be added_.

## Assumptions

- PRs come from branches of this repository; contributors are trusted to the level of
  write access (anyone with it could edit workflows anyway).
- Unit tests only: no database, network or browser; integration/E2E tests are out of scope.
- Design-system components, schemas/models and type-only files are excluded from scope,
  matching the project's existing coverage configuration.
- Tests run against the PR head, not the merge commit with the base branch.

## Limitations

- LLM output is non-deterministic; quality varies between runs and costs money per PR
  (bounded by the file cap, `--max-budget-usd`, turn limit and job timeouts).
- Tests are executed on the runner with network access; a malicious test could still make
  outbound requests (it cannot see the API key or a GitHub token).
- The bot's commit does not trigger `ci.yml` (a `GITHUB_TOKEN` property); the `verify` job
  runs the same checks on exactly that content, but there is no separate CI run on it.
- The agent cannot add shared test helpers or fixtures (`conftest.py`, `src/test/`) – by
  design – so it inlines small helpers.
- A rejected or failing patch is not partially applied; nothing is committed.
- Coverage is the metric shown; it does not prove the assertions are strong.

## What I would change for production

- Use a **GitHub App** token for the commit so CI re-runs on it, and a CODEOWNERS rule
  for `.github/` and `.claude/`.
- **Egress control** for the generate/verify jobs (e.g. step-security/harden-runner with
  an allowlist containing only the Anthropic API) and an ephemeral sandbox/container.
- **Mutation testing** (mutmut / Stryker) on changed lines to measure test strength, and
  a coverage gate on changed lines.
- Run on the merge commit, cache the Claude CLI and dependencies, and add a
  "suggest-only" mode that posts review suggestions instead of committing.
- Collect run metrics (decision accuracy, retries, cost, reviewer edits to generated tests)
  and an evaluation set of historical PRs to regression-test prompt/skill changes.
