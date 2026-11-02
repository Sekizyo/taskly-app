import pytest

from guard_paths import check


def added(path, mode="100644", body="+x = 1\n"):
    return (
        f"diff --git a/{path} b/{path}\nnew file mode {mode}\nindex 0000000..1111111\n"
        f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1 @@\n{body}"
    )


def modified(path, body="-a\n+b\n"):
    return (
        f"diff --git a/{path} b/{path}\nindex 1111111..2222222 100644\n"
        f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n{body}"
    )


@pytest.mark.parametrize("path", [
    "backend/tests/test_factory.py",
    "backend/tests/features/todos/test_router.py",
    "frontend/src/lib/http.test.ts",
    "frontend/src/features/todos/components/TodoList.test.tsx",
    "frontend/src/App.test.tsx",
])
def test_allows_added_or_modified_test_files(path):
    for patch in (added(path), modified(path)):
        result = check(patch)
        assert result["allowed"], result["violations"]


@pytest.mark.parametrize("path", [
    "backend/app/main.py",
    "backend/tests/conftest.py",
    "backend/tests/features/conftest.py",
    "frontend/src/lib/http.ts",
    "frontend/src/test/setup.ts",
    "frontend/package.json",
    ".github/workflows/ci.yml",
    ".claude/agents/test-engineer.md",
    "scripts/agent/guard_paths.py",
    "backend/tests/../app/main.py",
    "backend/tests/data.json",
    "frontend/src/x.test.ts.orig",
])
def test_rejects_non_test_paths(path):
    result = check(modified(path))
    assert not result["allowed"]
    assert any("not an allowed test path" in v for v in result["violations"])


def test_a_single_bad_file_rejects_the_whole_patch():
    result = check(added("backend/tests/test_ok.py") + modified("backend/app/factory.py"))
    assert not result["allowed"]
    assert [f["path"] for f in result["files"]] == ["backend/app/factory.py", "backend/tests/test_ok.py"]


@pytest.mark.parametrize("patch, label", [
    ("diff --git a/backend/tests/test_a.py b/backend/tests/test_a.py\ndeleted file mode 100644\n", "file deletion"),
    ("diff --git a/backend/tests/test_a.py b/backend/tests/test_b.py\nrename from backend/tests/test_a.py\n", "rename"),
    ("diff --git a/backend/tests/test_a.py b/backend/tests/test_a.py\nold mode 100644\nnew mode 100755\n", "mode change"),
    (added("backend/tests/test_link.py", mode="120000"), "unexpected file mode"),
    (added("backend/tests/test_exec.py", mode="100755"), "unexpected file mode"),
    ("diff --git a/frontend/src/a.test.ts b/frontend/src/a.test.ts\nGIT binary patch\nliteral 1\n", "binary content"),
])
def test_rejects_dangerous_patch_operations(patch, label):
    result = check(patch)
    assert not result["allowed"]
    assert any(label in v for v in result["violations"])


def test_content_lines_that_look_like_headers_are_ignored():
    body = "+old mode = 1\n+deleted file mode = 2\n+# rename from x\n"
    assert check(added("backend/tests/test_tricky.py", body=body))["allowed"]


def test_unparseable_diff_header_is_rejected():
    result = check('diff --git "a/backend/tests/t e s t.py" "b/backend/tests/t e s t.py"\n')
    assert not result["allowed"]


def test_empty_patch_is_neither_allowed_nor_a_violation():
    assert check("") == {"allowed": False, "empty": True, "files": [], "violations": []}


def test_limits_patch_size_and_file_count():
    many = "".join(added(f"backend/tests/test_{i}.py") for i in range(31))
    assert any("touches 31 files" in v for v in check(many)["violations"])
    huge = added("backend/tests/test_big.py", body="+" + "x" * 400_001 + "\n")
    assert any("exceeds" in v for v in check(huge)["violations"])
