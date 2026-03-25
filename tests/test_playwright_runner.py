import subprocess
import os
import sys
import shlex
import pytest


def _run_playwright(spec_path):
    # Ensure Playwright uses the test base URL
    env = os.environ.copy()
    env.setdefault('PLAYWRIGHT_BASE', 'http://127.0.0.1:8000')
    # Run playwright in headless mode and keep artifacts on failure (config in playwright.config.js)
    cmd = f"npx playwright test {shlex.quote(spec_path)} --reporter=list"
    proc = subprocess.Popen(cmd, shell=True, env=env)
    proc.wait()
    return proc.returncode


@pytest.mark.usefixtures('server')
def test_playwright_header_smoke():
    # Run the Playwright spec using the running test server (TEST_MODE=1 set by server fixture)
    spec = 'tests/playwright/header_smoke.spec.js'
    rc = _run_playwright(spec)
    # ensure artifacts are copied to a stable location for CI collection
    try:
        dest = os.path.join('test-artifacts', 'playwright')
        os.makedirs(dest, exist_ok=True)
        # copy known artifact folders if they exist
        for src in ('playwright-report', 'playwright-traces', 'playwright-screenshots'):
            if os.path.exists(src):
                # use tar to preserve tree (works in CI runner)
                tarpath = os.path.join(dest, src + '.tar')
                subprocess.call(['tar', '-cf', tarpath, src])
    except Exception:
        pass

    if rc != 0:
        pytest.fail(f'Playwright spec failed (exit code {rc}); see playwright-report for traces/screenshots')