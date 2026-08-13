# Makes tests/ a regular package so bare `python3 -m unittest` (implicit
# discovery) finds the suite from backend/. Without this file the directory is
# a PEP 420 namespace package, which unittest discovery has skipped since
# Python 3.11 — `python3 -m unittest tests.test_library` worked while plain
# `python3 -m unittest` silently ran nothing.
