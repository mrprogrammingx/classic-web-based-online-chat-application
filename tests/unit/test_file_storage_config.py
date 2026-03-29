"""Tests for file storage configuration."""

import os
import pytest
from pathlib import Path
import core.config as config


def test_file_storage_default_path():
    """Verify FILE_STORAGE_PATH defaults to ./uploads."""
    # Ensure env var is not set
    if 'FILE_STORAGE_PATH' in os.environ:
        del os.environ['FILE_STORAGE_PATH']
    
    path = config.FILE_STORAGE_PATH
    assert 'uploads' in path
    assert path == str(Path.cwd() / 'uploads')


def test_file_storage_custom_path():
    """Verify FILE_STORAGE_PATH can be customized via env var."""
    custom_path = '/tmp/custom_uploads'
    os.environ['FILE_STORAGE_PATH'] = custom_path
    
    try:
        # Force re-evaluation by accessing the attribute
        path = config.FILE_STORAGE_PATH
        assert path == custom_path
    finally:
        del os.environ['FILE_STORAGE_PATH']


def test_max_file_size_default():
    """Verify MAX_FILE_SIZE_BYTES defaults to 20 MB."""
    if 'MAX_FILE_SIZE_MB' in os.environ:
        del os.environ['MAX_FILE_SIZE_MB']
    
    size = config.MAX_FILE_SIZE_BYTES
    expected = 20 * 1024 * 1024  # 20 MB in bytes
    assert size == expected


def test_max_file_size_custom():
    """Verify MAX_FILE_SIZE_BYTES can be customized via env var."""
    os.environ['MAX_FILE_SIZE_MB'] = '50'
    
    try:
        size = config.MAX_FILE_SIZE_BYTES
        expected = 50 * 1024 * 1024  # 50 MB in bytes
        assert size == expected
    finally:
        del os.environ['MAX_FILE_SIZE_MB']


def test_max_image_size_default():
    """Verify MAX_IMAGE_SIZE_BYTES defaults to 3 MB."""
    if 'MAX_IMAGE_SIZE_MB' in os.environ:
        del os.environ['MAX_IMAGE_SIZE_MB']
    
    size = config.MAX_IMAGE_SIZE_BYTES
    expected = 3 * 1024 * 1024  # 3 MB in bytes
    assert size == expected


def test_max_image_size_custom():
    """Verify MAX_IMAGE_SIZE_BYTES can be customized via env var."""
    os.environ['MAX_IMAGE_SIZE_MB'] = '10'
    
    try:
        size = config.MAX_IMAGE_SIZE_BYTES
        expected = 10 * 1024 * 1024  # 10 MB in bytes
        assert size == expected
    finally:
        del os.environ['MAX_IMAGE_SIZE_MB']


def test_file_size_conversion():
    """Verify file sizes are correctly converted from MB to bytes."""
    os.environ['MAX_FILE_SIZE_MB'] = '100'
    os.environ['MAX_IMAGE_SIZE_MB'] = '5'
    
    try:
        file_size = config.MAX_FILE_SIZE_BYTES
        image_size = config.MAX_IMAGE_SIZE_BYTES
        
        assert file_size == 100 * 1024 * 1024
        assert image_size == 5 * 1024 * 1024
        
        # Verify file size is larger
        assert file_size > image_size
    finally:
        del os.environ['MAX_FILE_SIZE_MB']
        del os.environ['MAX_IMAGE_SIZE_MB']


def test_file_storage_in_exports():
    """Verify file storage config is exported in __all__."""
    assert 'FILE_STORAGE_PATH' in config.__all__
    assert 'MAX_FILE_SIZE_BYTES' in config.__all__
    assert 'MAX_IMAGE_SIZE_BYTES' in config.__all__
