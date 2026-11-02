import json

from render_report import MARKER, render, validate_agent_report

JUNIT = '<testsuites><testsuite tests="{t}" failures="{f}" errors="0" skipped="0"/></testsuites>'


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if isinstance(content, str) else json.dumps(content))


def test_renders_results_measured_by_the_workflow(tmp_path):
    write(tmp_path / "changes.json", {"backend": [{"path": "backend/app/core/config.py", "existing_tests": []}],
                                      "frontend": [], "skipped": []})
    write(tmp_path / "baseline/backend-junit.xml", JUNIT.format(t=3, f=0))
    write(tmp_path / "verify/backend-junit.xml", JUNIT.format(t=5, f=1))
    write(tmp_path / "baseline/backend-coverage.json",
          {"totals": {"percent_covered": 40.0}, "files": {"app/core/config.py": {"summary": {"percent_covered": 0.0}}}})
    write(tmp_path / "verify/backend-coverage.json",
          {"totals": {"percent_covered": 55.5}, "files": {"app/core/config.py": {"summary": {"percent_covered": 100.0}}}})
    write(tmp_path / "verify/status.json", {"backend tests": 1})
    body = render(tmp_path, "abcdef123", "https://run", "verification-failed")
    assert body.startswith(MARKER)
    assert "did not pass verification" in body
    assert "| backend | ✅ 3/3 passed | ❌ 4/5 passed, 1 failing | 40.0% → 55.5% (+15.5) |" in body
    assert "| `backend/app/core/config.py` | 0.0% | 100.0% (+100.0) |" in body
    assert "❌ backend tests" in body


def test_missing_artifacts_never_crash_rendering(tmp_path):
    body = render(tmp_path, "", "", "agent-failed")
    assert "agent run failed" in body


def test_agent_text_is_neutralised():
    report, problems = validate_agent_report({
        "summary": "ok <script>x</script> | @org/team",
        "skills_used": ["python-unit-tests", 5],
        "decisions": [
            {"source": "a.py", "action": "created", "test_file": "t.py", "reason": "r"},
            {"source": "b.py", "action": "rm -rf"},
            "garbage",
        ],
    })
    assert [d["source"] for d in report["decisions"]] == ["a.py"]
    assert report["skills_used"] == ["python-unit-tests"]
    assert len(problems) == 2


def test_rendered_decisions_escape_markdown_html_and_mentions(tmp_path):
    write(tmp_path / "agent/report.json", {
        "summary": "<img src=x onerror=alert(1)> @maintainer",
        "decisions": [{"source": "a|b.py", "action": "skipped", "reason": "pipe | here"}],
    })
    body = render(tmp_path, "", "", "no-changes")
    assert "<img" not in body
    assert "@maintainer" not in body
    assert "pipe \\| here" in body
