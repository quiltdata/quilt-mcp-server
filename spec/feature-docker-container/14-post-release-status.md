<!-- markdownlint-disable MD013 -->
# Post-Release Status Specification

## Overview

The post-release status system should reliably document release information in GitHub release notes and optionally post to associated pull requests. This specification defines the expected behavior and implementation approach.

## Goals

1. **Primary Goal**: ALWAYS append release status information to GitHub release notes
2. **Secondary Goal**: When a release originates from a PR, also post status as a PR comment
3. **Reliability**: Ensure release notes are updated even if PR detection fails
4. **Consistency**: Use the same formatted content for both destinations

## Release Status Information

The release status should include:

- Package version
- GitHub release URL
- PyPI/TestPyPI package URL
- Docker image URI (if built)
- Installation instructions appropriate for the release type (prod vs dev)
- Docker pull commands (if Docker image was built)

## Workflow Behavior

### Production Releases (push.yml)

When a production tag (`v*` excluding `v*-dev-*`) is pushed:

1. Build and publish packages
2. Create GitHub release with auto-generated notes
3. **Update the release notes** with formatted status information
4. Attempt to find associated PR (if any) and post comment

### Development Releases (pr.yml)

When a development tag (`v*-dev-*`) is pushed:

1. Build and publish to TestPyPI
2. Create GitHub release marked as pre-release
3. **Update the release notes** with formatted status information
4. Attempt to find associated PR and post comment

## Design Philosophy

### Pure Function Approach

The post-release status script follows a pure function design:
- All parameters are passed explicitly from the GitHub Action
- No environment variable dependencies (except GITHUB_TOKEN for API calls)
- No implicit behavior based on tag patterns or environment
- All decision logic happens in the GitHub Action, not the script
- Script focuses solely on formatting and posting status

This design ensures:
- Testability: All behavior can be tested with explicit inputs
- Predictability: No hidden dependencies or side effects
- Maintainability: Clear separation between orchestration (action) and execution (script)

## Implementation Requirements

### Release Notes Update (Primary)

The system MUST:

1. Use GitHub API to update the release body after creation
2. Append formatted status information to existing release notes
3. Preserve any auto-generated content from GitHub
4. Include clear section headers for the appended information
5. Handle both production and development releases appropriately

### PR Comment (Secondary)

The system SHOULD:

1. Attempt to find the PR associated with the release SHA
2. Post a formatted comment if PR is found
3. Gracefully continue if no PR is found (not an error)
4. Use the same formatting as release notes for consistency

### Error Handling

- **Release notes update failure**: Should be treated as an error and fail the workflow
- **PR detection failure**: Should be logged but not fail the workflow
- **PR comment failure**: Should be logged but not fail the workflow

## API Usage

### Updating Release Notes

```python
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
    # GET current release to preserve existing body
    # PATCH release with body + additional_content
    # Return success status
```

### Finding Associated PR

```python
def find_pr_for_sha(
    github_token: str,
    repo: str,
    sha: str,
) -> Optional[int]:
    """
    Find PR number associated with a commit SHA.

    Uses: GET /repos/{owner}/{repo}/commits/{sha}/pulls

    Returns PR number if found, None otherwise.
    """
```

## GitHub Actions Integration

### Action Outputs

The `create-release` action should output:

- `release-id`: GitHub release ID (for updating notes)
- `release-url`: Full URL to the release
- `pypi-url`: URL to PyPI/TestPyPI package
- `docker-image`: Docker image URI (if built)

### Script Parameters

The `post_release_status.py` script should accept ALL parameters explicitly (pure function design):

- `--release-id`: GitHub release ID for updating notes
- `--version`: Package version
- `--release-url`: GitHub release URL
- `--pypi-url`: PyPI package URL
- `--docker-image`: Docker image URI (optional)
- `--sha`: Git SHA for PR detection (optional)
- `--repo`: Repository identifier (owner/repo format)
- `--github-token`: API token
- `--is-production`: Boolean flag for production vs development release
- `--package-name`: Package name for display (e.g., "quilt-mcp-server")

### Workflow Steps

```yaml
- name: Create GitHub Release
  id: create-release
  uses: softprops/action-gh-release@v2
  # ... creates release, outputs release ID

- name: Post release status
  shell: bash
  env:
    GITHUB_TOKEN: ${{ github.token }}
  run: |
    uv run python scripts/post_release_status.py \
      --release-id "${{ steps.create-release.outputs.id }}" \
      --version "${{ inputs.package-version }}" \
      --release-url "${{ steps.create-release.outputs.url }}" \
      --pypi-url "${{ steps.package-urls.outputs.pypi-url }}" \
      --docker-image "${{ steps.docker-info.outputs.image-uri }}" \
      --sha "${{ github.sha }}" \
      --repo "${{ github.repository }}" \
      --github-token "${{ github.token }}" \
      --is-production "${{ inputs.is-production }}" \
      --package-name "quilt-mcp-server"
```

## Content Format

The formatted status content should be consistent between release notes and PR comments:

```markdown
---

## 📦 Release Artifacts

### Package Locations
- **GitHub Release:** [v{version}]({release_url})
- **PyPI Package:** [{package_name}]({pypi_url})
- **Docker Image:** `{docker_image}` (if applicable)

### Installation

#### From PyPI (Production)
```bash
pip install quilt-mcp-server=={version}
# or
uv add quilt-mcp-server=={version}
```

### From TestPyPI (Development)

```bash
pip install -i https://test.pypi.org/simple/ quilt-mcp-server=={version}
# or
uv add --index https://test.pypi.org/simple/ quilt-mcp-server=={version}
```

#### Docker (if applicable)

```bash
docker pull {docker_image}
```

## Success Criteria

1. Every GitHub release has complete status information in its notes
2. Release notes are updated reliably regardless of PR association
3. PR comments are posted when possible but don't block the workflow
4. Consistent formatting between release notes and PR comments
5. Clear error messages when release note updates fail
6. Graceful handling when PR detection/commenting fails

## Testing Strategy

### Manual Testing

1. Create a dev release from a PR branch - verify both release notes and PR comment
2. Create a dev release from a direct push - verify release notes only
3. Create a production release - verify release notes update
4. Test with missing Docker image - verify graceful handling
5. Test with invalid GitHub token - verify appropriate error

### Automated Testing

The `post_release_status.py` script should include:

- Unit tests for content generation
- Mock tests for GitHub API interactions
- Integration tests with test repository (if feasible)

## Migration Path

1. Update `post_release_status.py` to support `--release-id` parameter
2. Add `update_release_notes()` function to update existing releases
3. Modify logic to always update release notes first, then optionally comment on PR
4. Update GitHub Actions to pass release ID from `create-release` step
5. Test with development releases first
6. Deploy to production workflow

## Rollback Plan

If issues occur:

1. The script can be reverted while keeping the GitHub Actions changes
2. Manual release note updates can be performed if needed
3. Previous behavior (PR-only comments) can be restored quickly
