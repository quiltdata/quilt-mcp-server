<!-- markdownlint-disable MD013 -->
# Phase 2 Checklist — Publishing Automation

- [ ] Release workflow fails until container publish step exists
- [ ] GitHub Actions (or scripts) authenticate to AWS ECR using configured secrets
- [ ] Image pushes with version and `latest` tags
- [ ] Release artifacts log published image digest/URI
- [ ] Automated tests confirm publishing logic without requiring production access locally

