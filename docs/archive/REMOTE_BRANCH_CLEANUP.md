# Remote Branch Cleanup Request

## Summary
Local branch cleanup has been completed (25 → 10 branches), but the following branches still exist on remote repositories and need to be deleted by someone with admin permissions.

## Branches to Delete from `origin` Remote (fast-mcp-server)

```bash
git push origin --delete \
  15-productize-local-release \
  athena-tool \
  "cursor/identify-and-document-missing-quilt-features-3c02" \
  docs/workflow-documentation \
  feat/graphql-bucket-search \
  feature/json-schema-validation \
  feature/metadata-import-helpers \
  feature/package-tagging \
  feature/package-version-history \
  feature/table-output-formatting \
  fix/graphql-bucket-discovery \
  fix/inappropriate-bucket-search
```

## Branches to Delete from `quilt` Remote (quilt-mcp-server)

```bash
git push quilt --delete \
  15-productize-local-release \
  athena-tool \
  "cursor/identify-and-document-missing-quilt-features-3c02" \
  feature/json-schema-validation \
  feature/metadata-import-helpers \
  feature/package-tagging \
  feature/package-version-history \
  feature/table-output-formatting
```

## Reason for Deletion
These branches were identified as:
- **Already merged**: Work has been integrated into main
- **Stale**: Outdated work that has been superseded
- **Completed**: Automated work (like cursor agent) that has finished

## Local Cleanup Completed
✅ All these branches have been successfully deleted locally  
✅ 60% reduction in total branches (25 → 10)  
✅ All valuable work preserved in remaining active branches

## Action Required
Please run the above commands with admin permissions to sync the remote repositories with the local cleanup.


