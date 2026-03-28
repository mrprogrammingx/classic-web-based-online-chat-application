import os
import pytest
from test_playwright_runner import _run_playwright


@pytest.mark.skipif(False, reason="requires Playwright to be installed")
@pytest.mark.usefixtures('server')
def test_contacts_friends_playwright():
    spec = os.path.join('tests', 'e2e', 'playwright', 'contacts_friends.spec.js')
    rc = _run_playwright(spec)
    assert rc == 0, f'Playwright spec failed (exit code {rc})'
