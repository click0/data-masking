"""PyInstaller runtime hook: force UTF-8 for stdout/stderr on Windows.

This hook runs before any user code and prevents UnicodeEncodeError
when printing non-ASCII characters (e.g. Cyrillic) on Windows consoles
that default to cp1252 or other limited encodings.
"""
import sys
import io

if sys.platform == 'win32':
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
