# Script Analysis and Redesign Plan

## Current Script Ecosystem

### Core Scripts
1. **deploy.sh** - Main deployment orchestrator
2. **packager/package-lambda.sh** - Docker-based Lambda packaging with local testing
3. **scripts/post-deploy.sh** - Post-deployment configuration and basic validation
4. **tests/test-endpoint.sh** - Comprehensive endpoint testing (pre-auth design)
5. **scripts/common.sh** - Shared utilities and logging

### Testing Scripts  
6. **packager/run-lambda.sh** - Direct Lambda execution in Docker
7. **packager/test-lambda.sh** - Lambda testing with event generation
8. **tests/test_lambda.sh** - Unit testing for Lambda function

### Support Scripts
9. **scripts/cdk-deploy.sh** - CDK operations wrapper
10. **scripts/get_token.sh** - OAuth token retrieval
11. **scripts/check_logs.sh** - CloudWatch log viewing
12. **tests/generate_lambda_events.py** - Test event generation

## Current Issues

### 1. **Inconsistent Build Process**
- CDK uses built-in Lambda bundling (not our Docker packaging)
- Our Docker packaging works locally but isn't used in deployment
- No guarantee that "test locally == deploy remotely"

### 2. **Broken Test Integration**
- test-endpoint.sh doesn't support JWT authentication
- deploy.sh skips tests with --skip-tests flag to avoid failures
- No "test what you deploy" validation

### 3. **Poor Error Reporting**
- Failures are silent or unhelpful
- No automatic log checking on deployment failures
- Scripts don't integrate diagnostics

### 4. **Scattered Organization** 
- Related functionality split across directories
- No clear workflow documentation
- Inconsistent parameter patterns

## Redesign Goals

### A. **Consistent Docker-Based Builds**
- Force CDK to use our Docker-packaged Lambda code
- Ensure local testing uses identical packages to deployment
- Single source of truth for Lambda package creation

### B. **Integrated Test Pipeline**
- Pre-deployment: Test locally packaged Lambda
- Post-deployment: Test deployed endpoint with JWT auth
- Automatic failure diagnosis with log checking

### C. **Clear Workflow Organization**
```
1. Build (Docker package + local test)
2. Deploy (CDK with pre-built package)  
3. Validate (endpoint test + diagnostics)
4. Report (success summary or failure analysis)
```

### D. **Enhanced Error Reporting**
- Automatic log dumping on failures
- Clear failure categorization (build/deploy/runtime)
- Actionable error messages

## Implementation Plan

### Phase 1: Unified Build System
- Modify CDK to use pre-built Docker packages
- Ensure package-lambda.sh output is used by CDK
- Create build verification step

### Phase 2: Authentication-Aware Testing
- Update test-endpoint.sh to support JWT
- Integrate with get_token.sh for authentication
- Create comprehensive validation suite

### Phase 3: Error Diagnosis Integration
- Add automatic log checking to all scripts
- Create failure analysis functions
- Implement clear error categorization

### Phase 4: Workflow Integration
- Redesign deploy.sh as orchestrator
- Create clear success/failure reporting
- Add comprehensive documentation