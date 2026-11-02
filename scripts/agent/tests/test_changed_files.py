from changed_files import classify, parse_name_status


def run(lines, existing=(), max_files=20):
    return classify(parse_name_status("\n".join(lines)), set(existing), max_files)


def test_maps_backend_and_frontend_sources_to_test_locations():
    result = run(
        ["M\tbackend/app/features/todos/router.py", "A\tfrontend/src/lib/http.ts",
         "M\tfrontend/src/features/todos/components/TodoItem.tsx"],
        existing={"backend/tests/features/todos/test_router.py",
                  "frontend/src/features/todos/components/TodoItem.test.tsx"},
    )
    assert result["needs_agent"] is True
    assert result["stacks"] == ["backend", "frontend"]
    backend, = result["backend"]
    assert backend["existing_tests"] == ["backend/tests/features/todos/test_router.py"]
    http, item = result["frontend"]
    assert http["existing_tests"] == [] and http["suggested_test"] == "frontend/src/lib/http.test.ts"
    assert item["suggested_test"] == "frontend/src/features/todos/components/TodoItem.test.tsx"


def test_skips_declarations_wiring_styles_and_deleted_files():
    result = run([
        "M\tbackend/app/features/todos/schemas.py",
        "M\tbackend/app/__init__.py",
        "M\tbackend/app/main.py",
        "M\tfrontend/src/features/todos/types.ts",
        "M\tfrontend/src/design-system/components/Button/Button.styles.ts",
        "M\tfrontend/src/design-system/components/Button/Button.stories.tsx",
        "M\tfrontend/src/features/todos/index.ts",
        "D\tfrontend/src/lib/old.ts",
    ])
    assert result["needs_agent"] is False
    assert {item["path"]: item["reason"] for item in result["skipped"]}["frontend/src/lib/old.ts"] == "file deleted"
    assert len(result["skipped"]) == 8


def test_test_and_unrelated_changes_do_not_trigger_the_agent():
    result = run(["M\tbackend/tests/test_factory.py", "M\tfrontend/src/App.test.tsx",
                  "M\tREADME.md", "M\t.github/workflows/ci.yml", "M\tfrontend/src/styles.css"])
    assert result["needs_agent"] is False
    assert [t["path"] for t in result["tests_changed"]] == ["backend/tests/test_factory.py", "frontend/src/App.test.tsx"]
    assert result["other"] == ["README.md", ".github/workflows/ci.yml", "frontend/src/styles.css"]


def test_renames_use_the_new_path():
    result = run(["R087\tfrontend/src/lib/a.ts\tfrontend/src/lib/b.ts"])
    assert result["frontend"][0]["path"] == "frontend/src/lib/b.ts"


def test_scope_is_capped_and_overflow_is_reported():
    result = run([f"M\tbackend/app/module_{i}.py" for i in range(5)], max_files=3)
    assert result["truncated"] is True
    assert len(result["backend"]) == 3
    assert [s["reason"] for s in result["skipped"]] == ["over the 3-file limit"] * 2
