#!/usr/bin/env python3
"""Render the test-agent PR comment from the workflow's result artifacts.

Everything shown as a *result* (test counts, coverage, guard verdict) comes from files
produced by the workflow itself, not from the agent's self-report. The agent's report
is only used for its decisions and rationale, and is validated before use.

Expected layout of --dir (missing files are reported, never fatal):
    changes.json                   output of changed_files.py
    baseline/<stack>-junit.xml     tests on the PR head before the agent ran
    baseline/<stack>-coverage.json
    agent/report.json              structured report written by the agent
    agent/claude-result.json       `claude -p --output-format json` result (cost, turns)
    guard.json                     output of guard_paths.py
    verify/<stack>-junit.xml       tests after applying the agent patch (independent run)
    verify/<stack>-coverage.json
    verify/status.json             {"<check>": <exit code>, ...}
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MARKER = "<!-- taskly-test-agent -->"
STACKS = ("backend", "frontend")
VALID_ACTIONS = {"created", "updated", "skipped"}


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def junit_totals(path: Path) -> dict | None:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in totals:
            totals[key] += int(float(suite.get(key, 0) or 0))
    totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    return totals


def coverage_by_file(stack: str, data) -> tuple[float | None, dict[str, float]]:
    """Return (total line %, {repo-relative path: line %})."""
    if not data:
        return None, {}
    if stack == "backend":
        files = {
            f"backend/{name}": round(info["summary"]["percent_covered"], 1)
            for name, info in data.get("files", {}).items()
        }
        return round(data.get("totals", {}).get("percent_covered", 0.0), 1), files
    files = {}
    for name, info in data.items():
        if name == "total":
            continue
        marker = "/frontend/"
        relative = "frontend/" + name.split(marker, 1)[1] if marker in name else name
        files[relative] = round(info["lines"]["pct"], 1)
    return round(data.get("total", {}).get("lines", {}).get("pct", 0.0), 1), files


def validate_agent_report(report) -> tuple[dict | None, list[str]]:
    problems = []
    if not isinstance(report, dict):
        return None, ["agent report missing or not valid JSON"]
    decisions = report.get("decisions")
    if not isinstance(decisions, list):
        problems.append("`decisions` must be a list")
        decisions = []
    clean = []
    for item in decisions:
        if not isinstance(item, dict) or item.get("action") not in VALID_ACTIONS or not item.get("source"):
            problems.append(f"invalid decision entry: {str(item)[:80]}")
            continue
        clean.append({
            "source": str(item["source"])[:200],
            "action": item["action"],
            "test_file": str(item.get("test_file") or "")[:200],
            "reason": " ".join(str(item.get("reason") or "").split())[:300],
        })
    skills = [str(s)[:60] for s in report.get("skills_used", []) if isinstance(s, str)][:10]
    summary = " ".join(str(report.get("summary") or "").split())[:600]
    return {"decisions": clean, "skills_used": skills, "summary": summary}, problems


def escape(text: str) -> str:
    # Agent text is untrusted: neutralise markdown tables, HTML and @-mentions.
    return (text.replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")
            .replace("@", "@​").replace("\n", " "))


def fmt_pct(value: float | None) -> str:
    return "–" if value is None else f"{value:.1f}%"


def fmt_delta(before: float | None, after: float | None) -> str:
    if before is None or after is None:
        return ""
    delta = after - before
    return " (±0)" if abs(delta) < 0.05 else f" ({delta:+.1f})"


def fmt_tests(totals: dict | None) -> str:
    if not totals:
        return "not run"
    icon = "✅" if totals["failures"] == 0 and totals["errors"] == 0 and totals["tests"] > 0 else "❌"
    text = f"{icon} {totals['passed']}/{totals['tests']} passed"
    if totals["failures"] or totals["errors"]:
        text += f", {totals['failures'] + totals['errors']} failing"
    if totals["skipped"]:
        text += f", {totals['skipped']} skipped"
    return text


def render(directory: Path, sha: str, run_url: str, outcome: str) -> str:
    changes = load_json(directory / "changes.json") or {}
    guard = load_json(directory / "guard.json")
    status = load_json(directory / "verify" / "status.json") or {}
    claude_result = load_json(directory / "agent" / "claude-result.json") or {}
    report, problems = validate_agent_report(load_json(directory / "agent" / "report.json"))

    headline = {
        "committed": "✅ Tests generated, verified and committed to this branch.",
        "no-changes": "ℹ️ The agent reviewed the changes and decided no test changes were needed.",
        "skipped": "ℹ️ No testable source changes in this PR – the agent was not run.",
        "verification-failed": "❌ Generated tests did not pass verification – nothing was committed. The patch is attached to the workflow run for manual review.",
        "rejected": "⛔ The agent's patch touched files outside the allowed test paths and was rejected – nothing was committed.",
        "agent-failed": "⚠️ The agent run failed or exceeded its limits – nothing was committed.",
        "stale": "ℹ️ The branch moved while the agent was running – results were discarded; the newer commit gets its own run.",
    }.get(outcome, f"Outcome: `{outcome}`")

    lines = [MARKER, "## 🧪 Test agent report", "", headline, ""]
    lines.append(f"<sub>Commit `{sha[:7]}` · [workflow run]({run_url})</sub>")
    lines.append("")

    if report and report["summary"]:
        lines += [f"> {escape(report['summary'])}", ""]

    in_scope = changes.get("backend", []) + changes.get("frontend", [])
    if in_scope or changes.get("skipped"):
        lines += ["### Scope", "", "| Changed file | Stack | Existing tests |", "|---|---|---|"]
        for stack in STACKS:
            for item in changes.get(stack, []):
                existing = ", ".join(f"`{t}`" for t in item.get("existing_tests", [])) or "none"
                lines.append(f"| `{item['path']}` | {stack} | {existing} |")
        for item in changes.get("skipped", []):
            lines.append(f"| `{item['path']}` | – | skipped: {item['reason']} |")
        lines.append("")

    if report and report["decisions"]:
        lines += ["### Agent decisions", "", "| Source | Action | Test file | Reason |", "|---|---|---|---|"]
        for d in report["decisions"]:
            test_file = f"`{escape(d['test_file'])}`" if d["test_file"] else "–"
            lines.append(f"| `{escape(d['source'])}` | {d['action']} | {test_file} | {escape(d['reason'])} |")
        lines.append("")
    if report and report["skills_used"]:
        lines += ["**Skills used:** " + ", ".join(f"`{escape(s)}`" for s in report["skills_used"]), ""]

    if guard:
        if guard.get("files"):
            lines += ["### Files changed by the agent", ""]
            lines += [f"- `{f['path']}` ({f['status']})" for f in guard["files"]]
            lines.append("")
        if guard.get("violations"):
            lines += ["**Guard violations:**", ""] + [f"- {escape(v)}" for v in guard["violations"]] + [""]

    stacks = [s for s in STACKS if (directory / "baseline" / f"{s}-junit.xml").exists()
              or (directory / "verify" / f"{s}-junit.xml").exists()]
    if stacks:
        lines += ["### Test results (independent re-run)", "",
                  "| Stack | Before agent | After agent | Coverage before → after |", "|---|---|---|---|"]
        for stack in stacks:
            before_total, before_files = coverage_by_file(stack, load_json(directory / "baseline" / f"{stack}-coverage.json"))
            after_total, after_files = coverage_by_file(stack, load_json(directory / "verify" / f"{stack}-coverage.json"))
            lines.append(
                f"| {stack} | {fmt_tests(junit_totals(directory / 'baseline' / f'{stack}-junit.xml'))} "
                f"| {fmt_tests(junit_totals(directory / 'verify' / f'{stack}-junit.xml'))} "
                f"| {fmt_pct(before_total)} → {fmt_pct(after_total)}{fmt_delta(before_total, after_total)} |"
            )
        lines.append("")

        changed_rows = []
        for stack in stacks:
            _, before_files = coverage_by_file(stack, load_json(directory / "baseline" / f"{stack}-coverage.json"))
            _, after_files = coverage_by_file(stack, load_json(directory / "verify" / f"{stack}-coverage.json"))
            for item in changes.get(stack, []):
                path = item["path"]
                if path in before_files or path in after_files:
                    b, a = before_files.get(path), after_files.get(path)
                    changed_rows.append(f"| `{path}` | {fmt_pct(b)} | {fmt_pct(a)}{fmt_delta(b, a)} |")
        if changed_rows:
            lines += ["<details><summary>Line coverage of changed files</summary>", "",
                      "| File | Before | After |", "|---|---|---|", *changed_rows, "", "</details>", ""]

    if status:
        checks = " · ".join(f"{'✅' if code == 0 else '❌'} {name}" for name, code in status.items())
        lines += [f"**Verification checks:** {checks}", ""]

    meta = []
    if isinstance(claude_result.get("num_turns"), int):
        meta.append(f"{claude_result['num_turns']} turns")
    if isinstance(claude_result.get("total_cost_usd"), (int, float)):
        meta.append(f"${claude_result['total_cost_usd']:.2f}")
    if isinstance(claude_result.get("duration_ms"), int):
        meta.append(f"{claude_result['duration_ms'] / 1000:.0f}s")
    if problems:
        meta.append("report issues: " + "; ".join(escape(p) for p in problems[:3]))
    if meta:
        lines += [f"<sub>Agent run: {' · '.join(meta)}</sub>", ""]

    lines.append("<sub>Generated by the `test-engineer` agent. Add the `skip-test-agent` label to opt out. "
                 "Review generated tests like any other code.</sub>")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--sha", default="")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--outcome", required=True)
    args = parser.parse_args(argv)
    sys.stdout.write(render(args.dir, args.sha, args.run_url, args.outcome))
    return 0


if __name__ == "__main__":
    sys.exit(main())
