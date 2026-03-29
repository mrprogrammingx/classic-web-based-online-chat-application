# Stale Tab Cleanup Fix

## Issue
Users remained **AFK** after closing all browser tabs (without sending explicit close signal).

## Solution
Added automatic cleanup of tab records inactive for > 24 hours in `core/utils.py`:

```python
async def cleanup_stale_tabs(max_age_seconds: int = 86400):
    """Remove tab records that haven't been touched in max_age_seconds."""
```

- Runs automatically on every presence check
- Integrated into `get_presence_status()` and `get_presence_statuses()`
- Removes stale tabs, allowing accurate offline detection

## Result
✅ Users now show **offline** when all tabs are closed (within minutes, not days)  
✅ 7 new tests passing  
✅ 0 regressions  
✅ No database migrations needed

## Test Files
- `tests/unit/test_tab_cleanup.py` - 5 unit tests
- `tests/unit/test_tab_cleanup_scenario.py` - 2 scenario tests
