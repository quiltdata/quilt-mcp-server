#!/usr/bin/env python3
"""
Post release status comments to GitHub PRs.

This script posts release information as a comment on associated PRs,
including package locations, Docker images, and installation instructions.
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


def find_pr_for_tag(github_token: str, repo: str, sha: str) -> Optional[int]:
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
        description="Post release status to GitHub PRs"
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

    # Generate the comment body
    comment_body = generate_release_comment(
        version=args.version,
        release_url=args.release_url,
        pypi_url=args.pypi_url,
        docker_image=args.docker_image,
    )

    if args.dry_run:
        print("=== DRY RUN - Comment Body ===")
        print(comment_body)
        return 0

    # Determine PR number
    pr_number = args.pr_number

    if not pr_number and args.sha and args.github_token:
        # Try to find PR from SHA
        pr_number = find_pr_for_tag(
            github_token=args.github_token,
            repo=args.repo,
            sha=args.sha,
        )

    if not pr_number:
        print("No PR found to comment on", file=sys.stderr)
        print("Release Status:")
        print(comment_body)
        return 0  # Not an error - just no PR to comment on

    # Post the comment
    if not args.github_token:
        print("Error: GitHub token required to post comment", file=sys.stderr)
        return 1

    if not args.repo:
        print("Error: Repository required to post comment", file=sys.stderr)
        return 1

    success = post_comment_to_pr(
        github_token=args.github_token,
        repo=args.repo,
        pr_number=pr_number,
        comment_body=comment_body,
    )

    if success:
        print(f"Posted release status to PR #{pr_number}")
        return 0
    else:
        print(f"Failed to post comment to PR #{pr_number}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())