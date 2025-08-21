# Branch Protection Configuration

This document outlines the branch protection rules that should be configured in GitHub to enforce the branching strategy.

## 🔒 Branch Protection Rules

### **Main Branch (`main`)**
- ✅ **Require a pull request before merging**
  - Require approvals: **2**
  - Dismiss stale PR approvals when new commits are pushed
  - Require review from code owners
- ✅ **Require status checks to pass before merging**
  - Require branches to be up to date before merging
  - Status checks: `production-tests`, `production-security`, `production-build`
- ✅ **Require conversation resolution before merging**
- ✅ **Require signed commits**
- ✅ **Require linear history**
- ✅ **Restrict pushes that create files larger than 100 MB**
- ✅ **Restrict pushes that create files larger than 100 MB**

### **Develop Branch (`develop`)**
- ✅ **Require a pull request before merging**
  - Require approvals: **1**
  - Dismiss stale PR approvals when new commits are pushed
- ✅ **Require status checks to pass before merging**
  - Require branches to be up to date before merging
  - Status checks: `test`, `security-scan`, `build`
- ✅ **Require conversation resolution before merging**
- ✅ **Allow force pushes** (for maintainers only)
- ✅ **Allow deletions** (for maintainers only)

### **Staging Branch (`staging`)**
- ✅ **Require a pull request before merging**
  - Require approvals: **1**
  - Dismiss stale PR approvals when new commits are pushed
- ✅ **Require status checks to pass before merging**
  - Require branches to be up to date before merging
  - Status checks: `test-staging`, `security-audit`, `integration-test`
- ✅ **Require conversation resolution before merging**
- ✅ **Restrict pushes**
- ✅ **Require linear history**

## 🚫 Restricted Source Branches

### **Staging Branch Restrictions**
- **Only accepts PRs from:**
  - `develop` (manual PRs)
  - `develop-to-staging-*` (automated nightly builds)
- **Rejects PRs from:**
  - `feature/*` branches
  - `hotfix/*` branches
  - Any other branches

### **Main Branch Restrictions**
- **Only accepts PRs from:**
  - `staging` branch
- **Rejects PRs from:**
  - `develop` branch
  - `feature/*` branches
  - Any other branches

## 🔧 GitHub Settings Configuration

### **Repository Settings > Branches**

1. **Add rule for `main` branch:**
   ```
   Branch name pattern: main
   ✅ Require a pull request before merging
   ✅ Require approvals: 2
   ✅ Dismiss stale PR approvals when new commits are pushed
   ✅ Require review from code owners
   ✅ Require status checks to pass before merging
   ✅ Require branches to be up to date before merging
   ✅ Require conversation resolution before merging
   ✅ Require signed commits
   ✅ Require linear history
   ✅ Restrict pushes that create files larger than 100 MB
   ```

2. **Add rule for `develop` branch:**
   ```
   Branch name pattern: develop
   ✅ Require a pull request before merging
   ✅ Require approvals: 1
   ✅ Dismiss stale PR approvals when new commits are pushed
   ✅ Require status checks to pass before merging
   ✅ Require branches to be up to date before merging
   ✅ Require conversation resolution before merging
   ✅ Allow force pushes
   ✅ Allow deletions
   ```

3. **Add rule for `staging` branch:**
   ```
   Branch name pattern: staging
   ✅ Require a pull request before merging
   ✅ Require approvals: 1
   ✅ Dismiss stale PR approvals when new commits are pushed
   ✅ Require status checks to pass before merging
   ✅ Require branches to be up to date before merging
   ✅ Require conversation resolution before merging
   ✅ Restrict pushes
   ✅ Require linear history
   ```

4. **Add rule for feature branches:**
   ```
   Branch name pattern: feature/*
   ✅ Require a pull request before merging
   ✅ Require approvals: 1
   ✅ Require status checks to pass before merging
   ✅ Require branches to be up to date before merging
   ```

## 🚨 Enforcement Actions

### **Automated Enforcement**
- GitHub Actions workflows automatically validate PR source branches
- CI/CD pipelines enforce testing requirements
- Security scans run on all branches

### **Manual Enforcement**
- Repository administrators must configure branch protection rules
- Code owners must review production changes
- Team leads must approve staging deployments

## 📋 Required Status Checks

### **Feature → Develop**
- `test-feature`
- `security-check`

### **Develop → Staging**
- `test` (matrix)
- `security-scan`
- `build`

### **Staging → Main**
- `production-tests` (matrix)
- `production-security`
- `production-build`

## 🔐 Security Considerations

- **Signed commits required** for main branch
- **Security scans** run on all branches
- **Dependency vulnerability checks** on staging and main
- **License compliance** verification on production releases

## 📚 Additional Resources

- [GitHub Branch Protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/about-protected-branches)
- [Required Status Checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/troubleshooting-required-status-checks)
- [Code Owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
