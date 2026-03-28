"""Ensure all Python files in the workspace compile (syntax-only).

This is stricter than checking only git-tracked files and mirrors the
suggested shell command but provides nicer pytest output with file/line
context on failure.
"""
import compileall
from pathlib import Path
import pytest
import sys


EXCLUDE_DIRS = {'.git', '.venv', 'venv', 'env', 'node_modules', 'dist', 'build', '__pycache__'}


def _is_excluded(path: Path) -> bool:
    parts = {p for p in path.parts}
    return bool(parts & EXCLUDE_DIRS)


def _all_py_files() -> list[str]:
    base = Path('.')
    files = [str(p) for p in base.rglob('*.py') if not _is_excluded(p)]
    return sorted(files)


def test_all_python_files_compile():
    files = _all_py_files()
    assert files, "no python files found in workspace"

    errors: list[str] = []
    for f in files:
        try:
            src = Path(f).read_text(encoding='utf-8')
        except Exception as e:
            errors.append(f"{f}: could not read file: {e}")
            continue

        try:
            # use built-in compile to get SyntaxError with lineno and text
            compile(src, f, 'exec')
        except SyntaxError as se:
            # build a helpful message with location and offending line
            line = (se.text or '').strip() if se.text else ''
            errors.append(f"{f}:{se.lineno}:{se.offset}: {se.msg}\n    {line}")
        except Exception as e:
            errors.append(f"{f}: unexpected compile error: {e}")

    if errors:
        # join with newlines so pytest shows a readable failure
        pytest.fail("Syntax errors in Python files:\n" + "\n".join(errors))
