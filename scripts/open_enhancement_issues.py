#!/usr/bin/env python3
"""
Create GitHub enhancement issues from docs/ENHANCEMENT_ISSUES.md.

Usage:
  REPO="owner/repo" GITHUB_TOKEN="..." python scripts/open_enhancement_issues.py

Defaults:
  REPO defaults to the current repository remote if not provided.
  GITHUB_TOKEN must be a token with repo:issues scope.
"""

from __future__ import annotations

import os
import re
import sys
from typing import List, Tuple
import json
import subprocess
import urllib.request


ISSUES_MD = os.path.join(os.path.dirname(__file__), "..", "docs", "ENHANCEMENT_ISSUES.md")


def read_markdown_sections(path: str) -> List[Tuple[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # Split on level-3 headings that start with an ordinal pattern: ### N) Title
    parts = re.split(r"\n###\s+\d+\)\s+", text)
    headers = re.findall(r"\n###\s+(\d+\)\s+.+)\n", text)
    # If the file starts with content before first heading, drop it
    sections: List[Tuple[str, str]] = []
    for idx, header_line in enumerate(headers):
        # Extract title without the leading ordinal e.g., '1) Foo' -> 'Foo'
        title = re.sub(r"^\d+\)\s+", "", header_line).strip()
        body = parts[idx + 1] if idx + 1 < len(parts) else ""
        # Body stops before the next heading; strip trailing content after the next ###
        body = body.strip()
        sections.append((title, body))
    return sections


def discover_repo_fallback() -> str | None:
    try:
        out = subprocess.check_output(["git", "remote", "get-url", "origin"], text=True).strip()
        # Extract owner/repo from typical HTTPS URL
        m = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", out)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
    except Exception:
        return None
    return None


def create_issue(repo: str, token: str, title: str, body: str, labels: list[str]) -> dict:
    api_url = f"https://api.github.com/repos/{repo}/issues"
    data = json.dumps({"title": title, "body": body, "labels": labels}).encode("utf-8")
    req = urllib.request.Request(api_url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    repo = os.environ.get("REPO") or discover_repo_fallback()
    token = os.environ.get("GITHUB_TOKEN")
    if not repo:
        print("Error: REPO env var not set and could not infer from git remote.", file=sys.stderr)
        return 1
    if not token:
        print("Error: GITHUB_TOKEN env var must be set with repo:issues scope.", file=sys.stderr)
        return 1

    if not os.path.exists(ISSUES_MD):
        print(f"Error: {ISSUES_MD} not found.", file=sys.stderr)
        return 1

    sections = read_markdown_sections(os.path.abspath(ISSUES_MD))
    if not sections:
        print("No sections found. Ensure headings are formatted as '### N) Title'", file=sys.stderr)
        return 1

    created = []
    for title, body in sections:
        # Compose body with a standard header and link back to the doc
        full_body = body
        if "Acceptance criteria" not in body:
            full_body += "\n\nAcceptance criteria: see ENHANCEMENT_ISSUES.md."
        full_body += "\n\nSource: docs/ENHANCEMENT_ISSUES.md"
        issue = create_issue(repo=repo, token=token, title=title, body=full_body, labels=["enhancement", "quilt-parity"])
        created.append({"number": issue.get("number"), "title": issue.get("title"), "url": issue.get("html_url")})

    print(json.dumps({"created": created}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

