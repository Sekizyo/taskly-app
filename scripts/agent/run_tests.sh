#!/usr/bin/env bash
# Single entry point for running a stack's unit tests with machine-readable output.
# Used identically by CI, the PR workflow and the test-engineer agent, so "it passed
# for the agent" and "it passed in CI" mean the same thing.
#
#   scripts/agent/run_tests.sh backend   <out_dir> [extra pytest args / test paths]
#   scripts/agent/run_tests.sh frontend  <out_dir> [extra vitest args / test paths]
#   scripts/agent/run_tests.sh typecheck <out_dir>                  # frontend tsc (includes tests)
#   scripts/agent/run_tests.sh format    <out_dir> <files...>       # prettier --write (frontend files)
#   scripts/agent/run_tests.sh format-check <out_dir> <files...>    # prettier --check
#
# Test modes write <out_dir>/<stack>-junit.xml and <out_dir>/<stack>-coverage.json.
# Every mode exits with the underlying tool's exit code. File arguments for the
# format modes are repo-relative (frontend/src/...) and must be frontend test files.
set -euo pipefail

usage="usage: run_tests.sh backend|frontend|typecheck|format|format-check <out_dir> [args...]"
stack="${1:?$usage}"
out_dir="${2:?$usage}"
shift 2

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p "$out_dir"
out_dir="$(cd "$out_dir" && pwd)"

case "$stack" in
  backend)
    cd "$repo_root/backend"
    python_bin="python"
    [[ -x .venv/bin/python ]] && python_bin=".venv/bin/python"
    set +e
    "$python_bin" -m pytest -q -p no:cacheprovider \
      --junitxml="$out_dir/backend-junit.xml" \
      --cov=app --cov-branch --cov-report=term-missing:skip-covered \
      --cov-report="json:$out_dir/backend-coverage.json" \
      "$@"
    status=$?
    set -e
    ;;
  frontend)
    cd "$repo_root/frontend"
    set +e
    npx --no-install vitest run \
      --reporter=default --reporter=junit --outputFile.junit="$out_dir/frontend-junit.xml" \
      --coverage --coverage.reporter=text-summary --coverage.reporter=json-summary \
      --coverage.reportsDirectory="$out_dir/frontend-coverage" \
      "$@"
    status=$?
    set -e
    if [[ -f "$out_dir/frontend-coverage/coverage-summary.json" ]]; then
      cp "$out_dir/frontend-coverage/coverage-summary.json" "$out_dir/frontend-coverage.json"
    fi
    ;;
  typecheck)
    cd "$repo_root/frontend"
    set +e
    npx --no-install tsc --noEmit
    status=$?
    set -e
    ;;
  format|format-check)
    files=()
    for file in "$@"; do
      # Only frontend test files, given repo-relative; keeps this mode from being
      # usable to rewrite application code.
      if [[ ! "$file" =~ ^frontend/src/[A-Za-z0-9_./-]+\.test\.tsx?$ || "$file" == *..* ]]; then
        echo "refusing to format non-test file: $file" >&2
        exit 2
      fi
      files+=("${file#frontend/}")
    done
    [[ ${#files[@]} -eq 0 ]] && { echo "no files given" >&2; exit 2; }
    cd "$repo_root/frontend"
    flag="--write"; [[ "$stack" == "format-check" ]] && flag="--check"
    set +e
    npx --no-install prettier "$flag" "${files[@]}"
    status=$?
    set -e
    ;;
  *)
    echo "$usage" >&2
    exit 2
    ;;
esac

exit "$status"
