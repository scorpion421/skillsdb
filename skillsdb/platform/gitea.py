"""
Gitea platform integration: REST API client, autonomous repository management, and Git synchronization.
"""

import os
import sys
import json
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from ..config import DB_PATH

# Default connection settings for local Gitea instance
DEFAULT_GITEA_URL = "http://127.0.0.1:3000"
DEFAULT_GITEA_API = "http://127.0.0.1:3000/api/v1"
DEFAULT_GITEA_BOT = "Antigravity"
DEFAULT_GITEA_OWNER = "MickyFoley"
DEFAULT_GITEA_TOKEN = "7d867a712de35b13de78261a5ef72276b527c1e0"
DEFAULT_AUTHOR_NAME = "MickyFoley"
DEFAULT_AUTHOR_EMAIL = "scorpion.421@gmail.com"


def get_gitea_config() -> Dict[str, str]:
    """
    Resolves Gitea connection configuration from environment, local database, or defaults.
    """
    url = os.environ.get("GITEA_URL", DEFAULT_GITEA_URL).rstrip("/")
    token = os.environ.get("GITEA_TOKEN", DEFAULT_GITEA_TOKEN).strip()
    bot_user = os.environ.get("GITEA_BOT_USER", DEFAULT_GITEA_BOT).strip()
    default_owner = os.environ.get("GITEA_DEFAULT_OWNER", DEFAULT_GITEA_OWNER).strip()

    return {
        "url": url,
        "api_url": f"{url}/api/v1",
        "token": token,
        "bot_user": bot_user,
        "default_owner": default_owner,
    }


def _api_request(
    endpoint: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    timeout: float = 6.0,
) -> Tuple[int, Any]:
    """
    Executes an authenticated HTTP request to the Gitea REST API using standard library urllib.
    """
    config = get_gitea_config()
    endpoint = endpoint.lstrip("/")
    url = f"{config['api_url']}/{endpoint}"

    headers = {
        "Authorization": f"token {config['token']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"SkillsDB/{config['bot_user']}",
    }

    body_bytes = None
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            response_text = response.read().decode("utf-8")
            if not response_text:
                return status_code, {}
            try:
                return status_code, json.loads(response_text)
            except Exception:
                return status_code, response_text
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"error": err_body or str(exc)}
        return exc.code, parsed
    except Exception as exc:
        return 0, {"error": str(exc)}


def check_gitea_connection(timeout: float = 3.0) -> Dict[str, Any]:
    """
    Tests connectivity and authentication against the local Gitea instance.
    """
    config = get_gitea_config()
    status_code, data = _api_request("user", method="GET", timeout=timeout)

    if status_code == 200 and isinstance(data, dict):
        version_code, version_data = _api_request("version", method="GET", timeout=timeout)
        version_str = version_data.get("version", "unknown") if isinstance(version_data, dict) else "unknown"
        return {
            "connected": True,
            "url": config["url"],
            "version": version_str,
            "username": data.get("username", config["bot_user"]),
            "is_admin": data.get("is_admin", False),
            "email": data.get("email", ""),
        }
    return {
        "connected": False,
        "url": config["url"],
        "error": data.get("message") or data.get("error") or f"HTTP {status_code}",
    }


def create_or_get_repo(
    name: str,
    description: str = "",
    private: bool = True,
    owner: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Checks if a repository exists on Gitea; creates it if missing.
    """
    config = get_gitea_config()
    target_owner = owner or config["default_owner"]

    # 1. Check if repo already exists
    status_code, data = _api_request(f"repos/{target_owner}/{name}", method="GET")
    if status_code == 200 and isinstance(data, dict):
        return {
            "status": "exists",
            "name": name,
            "owner": target_owner,
            "clone_url": data.get("clone_url"),
            "html_url": data.get("html_url"),
            "private": data.get("private", True),
        }

    # 2. Create repo via admin endpoint or user endpoint
    payload = {
        "name": name,
        "description": description or f"Repository for {name}",
        "private": private,
        "auto_init": False,
    }

    create_code, create_data = _api_request(
        f"admin/users/{target_owner}/repos",
        method="POST",
        data=payload,
    )

    if create_code in (200, 201) and isinstance(create_data, dict):
        return {
            "status": "created",
            "name": name,
            "owner": target_owner,
            "clone_url": create_data.get("clone_url"),
            "html_url": create_data.get("html_url"),
            "private": create_data.get("private", True),
        }

    # Fallback to current authenticated user repo creation
    fallback_code, fallback_data = _api_request("user/repos", method="POST", data=payload)
    if fallback_code in (200, 201) and isinstance(fallback_data, dict):
        return {
            "status": "created",
            "name": name,
            "owner": fallback_data.get("owner", {}).get("login", config["bot_user"]),
            "clone_url": fallback_data.get("clone_url"),
            "html_url": fallback_data.get("html_url"),
            "private": fallback_data.get("private", True),
        }

    err_msg = create_data.get("message") or create_data.get("error") or f"HTTP {create_code}"
    return {
        "status": "error",
        "name": name,
        "owner": target_owner,
        "error": err_msg,
    }


def get_git_executable() -> Optional[str]:
    """Finds git executable path."""
    return shutil.which("git")


def _run_git(args: list, cwd: Path) -> subprocess.CompletedProcess:
    """Runs a git command with standard author environment variables."""
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = DEFAULT_AUTHOR_NAME
    env["GIT_AUTHOR_EMAIL"] = DEFAULT_AUTHOR_EMAIL
    env["GIT_COMMITTER_NAME"] = DEFAULT_AUTHOR_NAME
    env["GIT_COMMITTER_EMAIL"] = DEFAULT_AUTHOR_EMAIL

    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def is_git_repo(project_root: Path) -> bool:
    """Checks if a directory is inside an initialized git working tree."""
    if not (project_root / ".git").exists():
        res = _run_git(["rev-parse", "--is-inside-work-tree"], project_root)
        return res.returncode == 0
    return True


def get_remote_url(project_root: Path, remote_name: str = "origin") -> Optional[str]:
    """Returns remote URL for the specified remote name."""
    res = _run_git(["remote", "get-url", remote_name], project_root)
    if res.returncode == 0:
        return res.stdout.strip()
    return None


def init_gitea_workspace(
    project_root: Path,
    repo_name: Optional[str] = None,
    description: str = "",
    private: bool = True,
    owner: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Initializes git repository if necessary, provisions repo on Gitea, and sets origin remote.
    """
    if not get_git_executable():
        return {"status": "error", "error": "Git executable not found in PATH."}

    root = project_root.resolve()
    target_name = repo_name or root.name

    # Initialize git if needed
    if not (root / ".git").exists():
        _run_git(["init", "-b", "main"], root)

    config = get_gitea_config()
    target_owner = owner or config["default_owner"]

    repo_res = create_or_get_repo(target_name, description=description, private=private, owner=target_owner)
    if repo_res.get("status") == "error":
        return repo_res

    # Build authenticated clone URL for origin
    bot_user = config["bot_user"]
    token = config["token"]
    base_url = config["url"]
    auth_prefix = f"http://{bot_user}:{token}@"
    auth_base = base_url.replace("http://", auth_prefix)
    authenticated_remote = f"{auth_base}/{target_owner}/{target_name}.git"

    current_remote = get_remote_url(root, "origin")
    if current_remote:
        _run_git(["remote", "set-url", "origin", authenticated_remote], root)
    else:
        _run_git(["remote", "add", "origin", authenticated_remote], root)

    return {
        "status": "ready",
        "repo_name": target_name,
        "owner": target_owner,
        "remote_url": f"{config['url']}/{target_owner}/{target_name}.git",
        "html_url": repo_res.get("html_url"),
    }


def sync_to_gitea(
    project_root: Path,
    message: str = "Milestone update",
    push: bool = True,
    branch: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Stages changes, creates an atomic git commit, and pushes to Gitea origin.
    """
    if not is_git_repo(project_root):
        return {"status": "skipped", "reason": "Not a git repository."}

    root = project_root.resolve()

    # Stage changes
    _run_git(["add", "-A"], root)

    # Check status
    diff_res = _run_git(["diff", "--cached", "--quiet"], root)
    has_changes = diff_res.returncode != 0

    commit_hash = None
    if has_changes:
        commit_res = _run_git(["commit", "-m", message], root)
        if commit_res.returncode != 0:
            return {"status": "error", "error": commit_res.stderr.strip() or "Git commit failed."}

    # Retrieve current commit hash
    rev_res = _run_git(["rev-parse", "HEAD"], root)
    if rev_res.returncode == 0:
        commit_hash = rev_res.stdout.strip()

    if not commit_hash:
        return {"status": "clean", "committed": False, "pushed": False}

    pushed = False
    push_error = None

    if push:
        remote_url = get_remote_url(root, "origin")
        if remote_url:
            current_branch = branch
            if not current_branch:
                br_res = _run_git(["branch", "--show-current"], root)
                current_branch = br_res.stdout.strip() if br_res.returncode == 0 and br_res.stdout.strip() else "main"

            push_res = _run_git(["push", "-u", "origin", current_branch], root)
            if push_res.returncode == 0:
                pushed = True
            else:
                push_error = push_res.stderr.strip()

    return {
        "status": "synced" if (has_changes or pushed) else "clean",
        "has_changes": has_changes,
        "committed": has_changes,
        "commit_hash": commit_hash,
        "pushed": pushed,
        "push_error": push_error,
    }
