"""Persist Studio content to disk and commit it to GitHub on every Apply.

Uses the GitHub Contents API (HTTPS + token) so the API container does not need
a git binary or an interactive SSH key.
"""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .config import settings

log = logging.getLogger("dogar.github_sync")


def write_local(content: dict) -> Path | None:
    """Write site/content.json next to the live portfolio HTML."""
    root = Path(settings.site_path)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "content.json"
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def push_to_github(content: dict) -> dict:
    """Create a commit on GitHub with the latest portfolio content.

    Returns a small status dict for the Studio UI. Never raises to the caller —
    Apply must still succeed even if GitHub is misconfigured.
    """
    if not settings.github_sync_enabled:
        return {"ok": False, "skipped": True, "reason": "GITHUB_SYNC_ENABLED is false"}

    token = (settings.github_token or "").strip()
    repo = (settings.github_repo or "").strip().strip("/")
    if not token or not repo or "/" not in repo:
        return {
            "ok": False,
            "skipped": True,
            "reason": "Set GITHUB_TOKEN and GITHUB_REPO=owner/repo in .env",
        }

    branch = settings.github_branch or "main"
    path = (settings.github_content_path or "site/content.json").lstrip("/")
    text = json.dumps(content, ensure_ascii=False, indent=2) + "\n"
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    message = f"studio: update portfolio content ({stamp})"

    api = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        with httpx.Client(timeout=30.0, headers=headers) as client:
            sha = None
            current = client.get(api, params={"ref": branch})
            if current.status_code == 200:
                sha = current.json().get("sha")
            elif current.status_code not in (404,):
                return {
                    "ok": False,
                    "skipped": False,
                    "reason": f"GitHub read failed ({current.status_code})",
                }

            body = {
                "message": message,
                "content": encoded,
                "branch": branch,
            }
            if sha:
                body["sha"] = sha

            put = client.put(api, json=body)
            if put.status_code not in (200, 201):
                detail = put.text[:240]
                return {
                    "ok": False,
                    "skipped": False,
                    "reason": f"GitHub push failed ({put.status_code}): {detail}",
                }

            data = put.json()
            return {
                "ok": True,
                "skipped": False,
                "branch": branch,
                "path": path,
                "commit": (data.get("commit") or {}).get("sha"),
                "url": (data.get("content") or {}).get("html_url"),
            }
    except httpx.HTTPError as exc:
        log.exception("github sync failed")
        return {"ok": False, "skipped": False, "reason": str(exc)}


def sync_after_save(content: dict) -> dict:
    local_path = None
    try:
        local_path = write_local(content)
    except OSError as exc:
        log.exception("local content.json write failed")
        local = {"ok": False, "path": None, "reason": str(exc)}
    else:
        local = {"ok": True, "path": str(local_path) if local_path else None}

    github = push_to_github(content)
    return {"local": local, "github": github}
