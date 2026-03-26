import os
import pytest
from test_playwright_runner import _run_playwright


@pytest.mark.skipif(False, reason="requires Playwright to be installed")
@pytest.mark.usefixtures('server')
def test_me_badge_playwright():
    # Run the Playwright spec using the project's helper which sets PLAYWRIGHT_BASE
    spec = os.path.join('tests', 'e2e', 'playwright', 'me_badge.spec.js')
    rc = _run_playwright(spec)
    assert rc == 0, f'Playwright spec failed (exit code {rc})'
