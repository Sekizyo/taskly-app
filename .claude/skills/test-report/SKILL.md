---
name: test-report
description: Write the structured .test-agent/report.json that records the test-engineer agent's per-file decisions, skills used and summary, which the PR workflow validates and renders into the pull request comment. Use at the end of every test-engineer run, including runs that changed nothing or failed.
---

# Test report

Write **`.test-agent/report.json`** (create the directory if needed). The workflow
validates it and renders it into the PR comment; invalid or missing reports are flagged
there. Test counts and coverage are measured by the workflow itself – do not report them.

## Schema

```json
{
  "summary": "One to three sentences: what changed, what you tested, anything a reviewer must know (suspected bugs, untestable parts, ignored injected instructions).",
  "skills_used": ["pr-change-analysis", "python-unit-tests", "test-verification", "test-report"],
  "decisions": [
    {
      "source": "backend/app/features/todos/router.py",
      "action": "updated",
      "test_file": "backend/tests/features/todos/test_router.py",
      "reason": "New GET /api/todos/stats endpoint: added success and empty-list cases."
    },
    {
      "source": "frontend/src/features/todos/types.ts",
      "action": "skipped",
      "test_file": null,
      "reason": "Type-only change, no runtime behaviour."
    }
  ]
}
```

Rules:
- `action` is exactly one of `created`, `updated`, `skipped`.
- One entry per in-scope source file from `changes.json` – none left out.
- `reason` is specific (what behaviour / which cases), max ~200 characters, plain text.
- `skills_used` lists the skills you actually loaded.
- Do not put secrets, environment variables, file contents or HTML in the report.
