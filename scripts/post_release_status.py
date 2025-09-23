#!/usr/bin/env python3
"""
Post release status to GitHub releases and associated PRs.

This script updates GitHub release notes with release information and optionally
posts comments to associated PRs, including package locations, Docker images,
and installation instructions.

PRIMARY: Always update GitHub release notes (failure = workflow failure)
SECONDARY: Post PR comment when possible (failure = graceful continue)
"""

import argparse
import json
import os
import sys
from typing import Optional, Dict, Any


def generate_release_comment(
    version: str,
    release_url: str,
    pypi_url: str,
    docker_image: Optional[str] = None,
) -> str:
    """Generate the release status comment body."""
    is_prod = "-dev-" not in version

    body = f"## 🚀 Release Status for v{version}\n\n"
    body += "### 📦 Package Locations\n\n"
    body += f"- **GitHub Release:** [{release_url}]({release_url})\n"
    body += f"- **PyPI Package:** [{pypi_url}]({pypi_url})\n"

    if docker_image and docker_image != f"unknown/quilt-mcp-server:{version}":
        body += f"- **Docker Image:** `{docker_image}`\n"
        body += "\n### 🐳 Docker Pull Command\n"
        body += "```bash\n"
        body += f"docker pull {docker_image}\n"
        body += "```\n"

    body += "\n### 📥 Installation\n"
    if is_prod:
        body += "```bash\n"
        body += "# Install from PyPI\n"
        body += f"pip install quilt-mcp-server=={version}\n"
        body += "# or\n"
        body += f"uv add quilt-mcp-server=={version}\n"
        body += "```\n"
    else:
        body += "```bash\n"
        body += "# Install from TestPyPI\n"
        body += f"pip install -i https://test.pypi.org/simple/ quilt-mcp-server=={version}\n"
        body += "# or\n"
        body += f"uv add --index https://test.pypi.org/simple/ quilt-mcp-server=={version}\n"
        body += "```\n"

    return body


def update_release_notes(
    github_token: str,
    repo: str,
    release_id: str,
    additional_content: str,
) -> bool:
    """
    Update GitHub release notes by appending status information.

    Args:
        github_token: GitHub API token
        repo: Repository in "owner/repo" format
        release_id: GitHub release ID
        additional_content: Formatted status content to append

    Returns:
        True if successful, False otherwise
    """
    import requests

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # First, get the current release to preserve existing body
    get_url = f"https://api.github.com/repos/{repo}/releases/{release_id}"

    try:
        response = requests.get(get_url, headers=headers)
        response.raise_for_status()

        release_data = response.json()
        existing_body = release_data.get("body") or ""

        # Append the additional content
        updated_body = existing_body + additional_content

        # Update the release with the new body
        patch_url = f"https://api.github.com/repos/{repo}/releases/{release_id}"
        patch_data = {"body": updated_body}

        response = requests.patch(patch_url, headers=headers, json=patch_data)
        response.raise_for_status()

        return True

    except requests.RequestException as e:
        print(f"Error updating release notes: {e}", file=sys.stderr)
        return False


def find_pr_for_sha(github_token: str, repo: str, sha: str) -> Optional[int]:
    """
    Find the PR number associated with a git SHA.

    Args:
        github_token: GitHub API token
        repo: Repository in format "owner/repo"
        sha: Git commit SHA to search for

    Returns:
        PR number if found, None otherwise
    """
    import requests

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Search for PRs containing this commit
    url = f"https://api.github.com/repos/{repo}/commits/{sha}/pulls"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        pulls = response.json()
        if pulls:
            # Return the most recent PR
            return pulls[0]["number"]
    except requests.RequestException as e:
        print(f"Error searching for PRs: {e}", file=sys.stderr)

    return None


def find_pr_for_tag(github_token: str, repo: str, sha: str) -> Optional[int]:
    """
    Legacy alias for find_pr_for_sha for backward compatibility.

    Args:
        github_token: GitHub API token
        repo: Repository in format "owner/repo"
        sha: Git commit SHA to search for

    Returns:
        PR number if found, None otherwise
    """
    return find_pr_for_sha(github_token, repo, sha)


def post_comment_to_pr(
    github_token: str,
    repo: str,
    pr_number: int,
    comment_body: str,
) -> bool:
    """
    Post a comment to a GitHub PR.

    Args:
        github_token: GitHub API token
        repo: Repository in format "owner/repo"
        pr_number: PR number to comment on
        comment_body: Comment text to post

    Returns:
        True if successful, False otherwise
    """
    import requests

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    data = {"body": comment_body}

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Error posting comment: {e}", file=sys.stderr)
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Post release status to GitHub releases and PRs"
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Package version",
    )
    parser.add_argument(
        "--release-url",
        required=True,
        help="GitHub release URL",
    )
    parser.add_argument(
        "--pypi-url",
        required=True,
        help="PyPI package URL",
    )
    parser.add_argument(
        "--docker-image",
        help="Docker image URI",
    )
    parser.add_argument(
        "--release-id",
        help="GitHub release ID for updating notes",
    )
    parser.add_argument(
        "--pr-number",
        type=int,
        help="PR number to comment on (if known)",
    )
    parser.add_argument(
        "--sha",
        help="Git SHA to find associated PR",
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="GitHub repository (owner/repo format)",
    )
    parser.add_argument(
        "--github-token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub API token",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print comment without posting",
    )

    args = parser.parse_args()

    # Generate the status content
    status_content = generate_release_comment(
        version=args.version,
        release_url=args.release_url,
        pypi_url=args.pypi_url,
        docker_image=args.docker_image,
    )

    if args.dry_run:
        print("=== DRY RUN - Comment Body ===")
        print(status_content)
        return 0

    # PRIMARY GOAL: Update release notes if release-id is provided
    if args.release_id:
        if not args.github_token:
            print("Error: GitHub token required to update release notes", file=sys.stderr)
            return 1

        if not args.repo:
            print("Error: Repository required to update release notes", file=sys.stderr)
            return 1

        # Format content for release notes (add separator)
        release_notes_content = f"\n---\n\n{status_content}"

        success = update_release_notes(
            github_token=args.github_token,
            repo=args.repo,
            release_id=args.release_id,
            additional_content=release_notes_content,
        )

        if not success:
            print("Failed to update release notes", file=sys.stderr)
            return 1  # CRITICAL: Release notes update failure should fail the workflow

        print(f"Updated release notes for release {args.release_id}")

    # SECONDARY GOAL: Post PR comment if possible (failure = graceful continue)
    pr_number = args.pr_number

    if not pr_number and args.sha and args.github_token:
        # Try to find PR from SHA
        pr_number = find_pr_for_sha(
            github_token=args.github_token,
            repo=args.repo,
            sha=args.sha,
        )

    if pr_number and args.github_token and args.repo:
        # Attempt to post PR comment
        pr_success = post_comment_to_pr(
            github_token=args.github_token,
            repo=args.repo,
            pr_number=pr_number,
            comment_body=status_content,
        )

        if pr_success:
            print(f"Posted release status to PR #{pr_number}")
        else:
            print(f"Warning: Failed to post comment to PR #{pr_number}", file=sys.stderr)
            # Don't fail the workflow for PR comment failures
    elif not args.release_id:
        # Legacy behavior: if no release-id and no PR found, show status
        print("No PR found to comment on", file=sys.stderr)
        print("Release Status:")
        print(status_content)

    return 0


if __name__ == "__main__":
    sys.exit(main())