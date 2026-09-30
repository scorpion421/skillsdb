"""
Platform utilities: Windows UTF-8 manifests and environment variables.
"""

from .windows_utf8 import check_windows_utf8, fix_utf8

__all__ = [
    "check_windows_utf8",
    "fix_utf8",
]
