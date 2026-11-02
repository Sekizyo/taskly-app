#!/usr/bin/env python3
"""Validate that an agent-produced patch only adds or edits unit-test files.

This is the hard security boundary between the LLM and the repository: whatever the
agent was told or tricked into doing (e.g. via prompt injection in PR content), a
patch is only ever applied if every hunk targets an allowed test path.

Rejected: paths outside the allowlist, path traversal, deletions, renames/copies,
mode changes, symlinks, submodules, binary content, and oversized patches.

Usage:
    guard_paths.py agent.patch > guard.json   # exit 0 = allowed, 1 = rejected
"""
from __future__ import annotations

import fnmatch
import json
import re
import sys

ALLOWED = [
    "backend/tests/*.py",
    "backend/tests/**/*.py",
    "frontend/src/**/*.test.ts",
    "frontend/src/**/*.test.tsx",
    "frontend/src/*.test.ts",
    "frontend/src/*.test.tsx",
]
MAX_FILES = 30
MAX_PATCH_BYTES = 400_000

HEADER = re.compile(r"^diff --git a/(?P<a>\S+) b/(?P<b>\S+)$")
FORBIDDEN_MARKERS = {
    "deleted file mode": "file deletion",
    "rename from": "rename",
    "copy from": "copy",
    "old mode": "mode change",
    "new mode": "mode change",
    "GIT binary patch": "binary content",
    "Binary files": "binary content",
}
SAFE_PATH = re.compile(r"^[A-Za-z0-9_./-]+$")


def path_allowed(path: str) -> bool:
    parts = path.split("/")
    if ".." in parts or path.startswith("/") or not SAFE_PATH.match(path):
        return False
    if parts[-1] == "conftest.py":
        # Shared fixtures/plugins change how *every* test runs; humans own those.
        return False
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in ALLOWED)


def check(patch: str) -> dict:
    files: dict[str, dict] = {}
    violations: list[str] = []
    current: str | None = None

    if len(patch.encode()) > MAX_PATCH_BYTES:
        violations.append(f"patch exceeds {MAX_PATCH_BYTES} bytes")

    for line in patch.splitlines():
        header = HEADER.match(line)
        if header:
            a, b = header["a"], header["b"]
            current = b
            if a != b:
                violations.append(f"{b}: path changed from {a}")
            files[current] = {"path": current, "status": "modified"}
            if not path_allowed(current):
                violations.append(f"{current}: not an allowed test path")
            continue
        if line.startswith("diff ") and not header:
            violations.append(f"unparseable diff header: {line[:120]}")
            continue
        if current is None:
            continue
        if line.startswith("new file mode"):
            files[current]["status"] = "added"
            if not line.endswith("100644"):
                violations.append(f"{current}: unexpected file mode {line.split()[-1]}")
        elif line.startswith("index ") and line.split()[-1] in {"120000", "160000"}:
            violations.append(f"{current}: symlink or submodule")
        else:
            for marker, label in FORBIDDEN_MARKERS.items():
                if line.startswith(marker):
                    violations.append(f"{current}: {label}")

    if len(files) > MAX_FILES:
        violations.append(f"patch touches {len(files)} files (limit {MAX_FILES})")

    return {
        "allowed": not violations and bool(files),
        "empty": not files,
        "files": sorted(files.values(), key=lambda item: item["path"]),
        "violations": sorted(set(violations)),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8", errors="replace") as handle:
        result = check(handle.read())
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result["allowed"] or result["empty"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
