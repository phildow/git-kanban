#!/usr/bin/env bash
set -euo pipefail

VERBOSE=false
COMMAND=""

for arg in "$@"; do
  case "$arg" in
    -v|--verbose) VERBOSE=true ;;
    -*) echo "Unknown flag: $arg"; exit 1 ;;
    *) COMMAND="$arg" ;;
  esac
done

run_tests() {
  if $VERBOSE; then
    python -m pip install -e ".[dev]"
    python -m pytest -n auto
  else
    python -m pip install -e ".[dev]" &> /dev/null
    python -m pytest -n auto -q 2>&1 | tail -5
  fi
}

run_install() {
  python -m pip install -e . -q
}

run_typecheck() {
  if $VERBOSE; then
    python -m pip install -e ".[dev]"
    python -m mypy
  else
    python -m pip install -e ".[dev]" &> /dev/null
    python -m mypy 2>&1 | tail -1
  fi
}

case "$COMMAND" in
  tests)
    run_tests
    ;;
  install)
    run_install
    ;;
  typecheck)
    run_typecheck
    ;;
  *)
    echo "Usage: $0 [-v|--verbose] <command>"
    echo ""
    echo "Commands:"
    echo "  tests       Run the test suite"
    echo "  install     Install the package and launch the REPL"
    echo "  typecheck   Run static type checks"
    exit 1
    ;;
esac
