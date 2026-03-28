import os
import pytest
from test_playwright_runner import _run_playwright


@pytest.mark.usefixtures('server')
def test_friends_navigate_playwright():
    spec = os.path.join('tests', 'e2e', 'playwright', 'friends_navigate_to_chat.spec.js')
    rc = _run_playwright(spec)
    assert rc == 0, f'Playwright spec failed (exit code {rc})'
