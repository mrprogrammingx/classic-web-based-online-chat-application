# File Storage Configuration Implementation

## Summary
Added centralized file storage configuration to `core/config.py` for managing upload locations and file size limits.

## Implementation

### Configuration Added (`core/config.py`)
Three new lazy-evaluated configuration parameters:

1. **`FILE_STORAGE_PATH`** - Directory for storing uploaded files
   - Environment: `FILE_STORAGE_PATH`
   - Default: `./uploads`
   - Type: String path

2. **`MAX_FILE_SIZE_BYTES`** - Maximum file upload size
   - Environment: `MAX_FILE_SIZE_MB` (in MB, converted to bytes)
   - Default: 20 MB
   - Type: Integer bytes

3. **`MAX_IMAGE_SIZE_BYTES`** - Maximum image upload size
   - Environment: `MAX_IMAGE_SIZE_MB` (in MB, converted to bytes)
   - Default: 3 MB
   - Type: Integer bytes

### Storage Details
- **Location**: Local file system at configured path
- **Maximum file size**: 20 MB (configurable)
- **Maximum image size**: 3 MB (configurable)

## Tests
**8 new tests** in `tests/unit/test_file_storage_config.py`:
- ✅ Default path verification
- ✅ Custom path configuration
- ✅ Default file size (20 MB)
- ✅ Custom file size
- ✅ Default image size (3 MB)
- ✅ Custom image size
- ✅ Size conversion (MB to bytes)
- ✅ Export verification

## Usage Example

```python
# Import configuration
from core.config import FILE_STORAGE_PATH, MAX_FILE_SIZE_BYTES, MAX_IMAGE_SIZE_BYTES

# Use in file upload handler
def handle_upload(file):
    if file.size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File too large. Max: {MAX_FILE_SIZE_BYTES} bytes")
    
    filepath = Path(FILE_STORAGE_PATH) / file.filename
    with open(filepath, 'wb') as f:
        f.write(file.read())
```

## Environment Configuration

```bash
# Custom storage directory
export FILE_STORAGE_PATH=/mnt/uploads

# Increase max file size to 100 MB
export MAX_FILE_SIZE_MB=100

# Increase max image size to 10 MB
export MAX_IMAGE_SIZE_MB=10
```

## Compatibility
- ✅ No breaking changes
- ✅ Backward compatible
- ✅ Existing code unaffected
- ✅ All tests passing (34/34 for file storage + cleanup + smoke)

## Files Modified/Created
1. **`core/config.py`** - Added 3 new configuration functions
2. **`tests/unit/test_file_storage_config.py`** - Added 8 comprehensive tests
3. **`FILE_STORAGE_CONFIG.md`** - Configuration documentation

---

**Status**: ✅ Complete and tested  
**Ready for**: Immediate use in upload handlers
