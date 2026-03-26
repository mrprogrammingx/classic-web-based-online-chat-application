Playwright end-to-end tests
===========================

This folder contains Playwright specs that exercise the running application in a real browser.

Run a single spec locally:

```bash
# ensure Playwright browsers are installed once
npx playwright install
npx playwright test tests/e2e/playwright/reply_preview.spec.js
```

Helpers (registerUser, createPrivateRoomAndInvite) live in `helpers.js` alongside the specs.
