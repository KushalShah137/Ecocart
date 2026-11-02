#!/usr/bin/env bash
# Runs the whole suite. Oracle integration tests are skipped automatically when the DB is unreachable.
cd "$(dirname "$0")/.." && python -m pytest -v
