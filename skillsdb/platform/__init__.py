"""
Platform utilities: Windows UTF-8 manifests and native MCP JSON-RPC server.
"""

from .windows_utf8 import check_windows_utf8, fix_utf8
from .mcp_server import run_mcp_server
from .gitea import (
    check_gitea_connection,
    create_or_get_repo,
    init_gitea_workspace,
    sync_to_gitea,
    get_gitea_config,
    ensure_gitignore,
    find_gitea_executable,
    start_gitea_server,
)

__all__ = [
    "check_windows_utf8",
    "fix_utf8",
    "run_mcp_server",
    "check_gitea_connection",
    "create_or_get_repo",
    "init_gitea_workspace",
    "sync_to_gitea",
    "get_gitea_config",
    "ensure_gitignore",
    "find_gitea_executable",
    "start_gitea_server",
]
