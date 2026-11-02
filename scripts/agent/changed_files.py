#!/usr/bin/env python3
"""Deterministically classify a PR's changed files for the test-engineer agent.

The LLM decides *how* to test; this script decides *what is in scope*. Keeping the
scoping deterministic makes runs reproducible, lets the workflow skip the (paid)
agent entirely when nothing testable changed, and bounds the work per run.

Usage:
    changed_files.py --base <sha> --head <sha> [--max-files N] > changes.json
    changed_files.py --name-status-file diff.txt               > changes.json
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import PurePosixPath

DEFAULT_MAX_FILES = 20

BACKEND_SOURCE = ["backend/app/*.py", "backend/app/**/*.py"]
BACKEND_TESTS = ["backend/tests/*.py", "backend/tests/**/*.py"]
FRONTEND_SOURCE = ["frontend/src/**/*.ts", "frontend/src/**/*.tsx", "frontend/src/*.ts", "frontend/src/*.tsx"]
FRONTEND_TESTS = ["frontend/src/**/*.test.ts", "frontend/src/**/*.test.tsx", "frontend/src/*.test.ts", "frontend/src/*.test.tsx"]

# Code with no behaviour worth unit testing (declarations, wiring, styling, stories).
# Mirrors the coverage exclusions in backend/pyproject.toml and frontend/vite.config.ts.
SKIP_PATTERNS = {
    "package marker": ["*/__init__.py"],
    "entrypoint": ["backend/app/main.py", "frontend/src/main.tsx"],
    "declarative schema/model": ["backend/app/**/schemas.py", "backend/app/**/models.py",
                                 "backend/app/**/types.py", "backend/app/**/constants.py"],
    "type declarations": ["frontend/src/**/types.ts", "frontend/src/**/*.types.ts", "frontend/src/**/*.d.ts"],
    "barrel file": ["frontend/src/**/index.ts"],
    "styles": ["frontend/src/**/*.styles.ts", "frontend/src/**/GlobalStyles.ts"],
    "storybook story": ["frontend/src/**/*.stories.tsx"],
    "test helper": ["frontend/src/test/**", "frontend/src/design-system/mocks.tsx"],
    "constants": ["frontend/src/**/constants.ts", "frontend/src/**/*.constants.ts",
                  "frontend/src/features/*/api/queryKeys.ts"],
}


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def skip_reason(path: str) -> str | None:
    for reason, patterns in SKIP_PATTERNS.items():
        if matches(path, patterns):
            return reason
    return None


def backend_test_candidates(path: str) -> list[str]:
    # backend/app/features/todos/router.py -> backend/tests/features/todos/test_router.py
    relative = PurePosixPath(path).relative_to("backend/app")
    return [str(PurePosixPath("backend/tests") / relative.parent / f"test_{relative.name}")]


def frontend_test_candidates(path: str) -> list[str]:
    # frontend/src/lib/http.ts -> frontend/src/lib/http.test.ts(x), colocated
    source = PurePosixPath(path)
    stem = source.name.rsplit(".", 1)[0]
    return [str(source.with_name(f"{stem}.test.ts")), str(source.with_name(f"{stem}.test.tsx"))]


def classify(entries: list[tuple[str, str]], existing: set[str], max_files: int) -> dict:
    result: dict = {
        "backend": [], "frontend": [], "skipped": [],
        "tests_changed": [], "other": [], "truncated": False,
    }
    for status, path in entries:
        kind = status[0]
        if matches(path, BACKEND_TESTS) or matches(path, FRONTEND_TESTS):
            result["tests_changed"].append({"path": path, "status": kind})
            continue
        stack = "backend" if matches(path, BACKEND_SOURCE) else "frontend" if matches(path, FRONTEND_SOURCE) else None
        if stack is None:
            result["other"].append(path)
            continue
        reason = "file deleted" if kind == "D" else skip_reason(path)
        if reason:
            result["skipped"].append({"path": path, "reason": reason})
            continue
        candidates = backend_test_candidates(path) if stack == "backend" else frontend_test_candidates(path)
        result[stack].append({
            "path": path,
            "status": kind,
            "existing_tests": [c for c in candidates if c in existing],
            "suggested_test": next((c for c in candidates if c in existing), candidates[-1] if path.endswith(".tsx") else candidates[0]),
        })

    in_scope = result["backend"] + result["frontend"]
    if len(in_scope) > max_files:
        keep = {item["path"] for item in in_scope[:max_files]}
        for stack in ("backend", "frontend"):
            dropped = [item for item in result[stack] if item["path"] not in keep]
            result[stack] = [item for item in result[stack] if item["path"] in keep]
            result["skipped"] += [{"path": item["path"], "reason": f"over the {max_files}-file limit"} for item in dropped]
        result["truncated"] = True

    result["needs_agent"] = bool(result["backend"] or result["frontend"])
    result["stacks"] = [s for s in ("backend", "frontend") if result[s]]
    return result


def parse_name_status(text: str) -> list[tuple[str, str]]:
    entries = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        # Renames/copies list old and new path; the new path is what changed.
        entries.append((status, parts[-1]))
    return entries


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--name-status-file")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    args = parser.parse_args(argv)

    if args.name_status_file:
        with open(args.name_status_file, encoding="utf-8") as handle:
            diff = handle.read()
    elif args.base:
        diff = git("diff", "--name-status", "-M", f"{args.base}...{args.head}")
    else:
        parser.error("--base or --name-status-file is required")

    existing = set(git("ls-files").splitlines()) if not args.name_status_file else set()
    json.dump(classify(parse_name_status(diff), existing, args.max_files), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
