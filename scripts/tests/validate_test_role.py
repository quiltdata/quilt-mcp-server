#!/usr/bin/env python3
"""
Validate QUILT_TEST_ROLE_ARN for JWT testing.

This script validates that the test role ARN is:
1. Present in environment
2. Syntactically valid
3. Assumable by current AWS credentials
4. Has necessary permissions for MCP testing

Usage:
    python scripts/tests/validate_test_role.py
    python scripts/tests/validate_test_role.py --role-arn arn:aws:iam::123456789:role/TestRole
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv


def validate_arn_format(arn: str) -> Tuple[bool, str]:
    """Validate ARN format and extract components."""
    # Updated pattern to handle nested role paths like /quilt/quilt-staging/us-east-1/RoleName
    arn_pattern = r'^arn:aws:iam::(\d{12}):role/(.+)$'
    match = re.match(arn_pattern, arn)
    
    if not match:
        return False, "Invalid ARN format. Expected: arn:aws:iam::ACCOUNT-ID:role/ROLE-PATH"
    
    account_id, role_path = match.groups()
    role_name = role_path.split('/')[-1]  # Get the actual role name (last part)
    return True, f"Valid ARN format - Account: {account_id}, Role: {role_name}, Path: {role_path}"


def get_current_identity() -> Tuple[bool, str, Optional[Dict]]:
    """Get current AWS identity."""
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        return True, f"Current identity: {identity['Arn']}", identity
    except NoCredentialsError:
        return False, "No AWS credentials found. Configure AWS credentials first.", None
    except ClientError as e:
        return False, f"Failed to get AWS identity: {e}", None


def test_role_assumption(role_arn: str) -> Tuple[bool, str, Optional[Dict]]:
    """Test if the role can be assumed."""
    try:
        sts = boto3.client('sts')
        
        # Attempt to assume the role
        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='quilt-mcp-test-validation',
            DurationSeconds=900  # 15 minutes minimum
        )
        
        credentials = response['Credentials']
        assumed_role_arn = response['AssumedRoleUser']['Arn']
        
        return True, f"✅ Successfully assumed role: {assumed_role_arn}", credentials
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        
        if error_code == 'AccessDenied':
            return False, f"❌ Access denied assuming role: {error_msg}", None
        elif error_code == 'InvalidUserType':
            return False, f"❌ Invalid user type for role assumption: {error_msg}", None
        else:
            return False, f"❌ Role assumption failed ({error_code}): {error_msg}", None


def test_role_permissions(credentials: Dict) -> List[Tuple[str, bool, str]]:
    """Test if assumed role has necessary permissions."""
    # Create clients with assumed role credentials
    session = boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )
    
    s3 = session.client('s3')
    iam = session.client('iam')
    
    tests = []
    
    # Test S3 permissions
    try:
        s3.list_buckets()
        tests.append(("S3 ListBuckets", True, "Can list S3 buckets"))
    except ClientError as e:
        tests.append(("S3 ListBuckets", False, f"Cannot list buckets: {e.response['Error']['Code']}"))
    
    # Test IAM permissions
    try:
        iam.list_roles(MaxItems=1)
        tests.append(("IAM ListRoles", True, "Can list IAM roles"))
    except ClientError as e:
        tests.append(("IAM ListRoles", False, f"Cannot list roles: {e.response['Error']['Code']}"))
    
    # Test STS permissions (should work since we just assumed the role)
    try:
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        tests.append(("STS GetCallerIdentity", True, f"Identity: {identity['Arn']}"))
    except ClientError as e:
        tests.append(("STS GetCallerIdentity", False, f"Cannot get identity: {e.response['Error']['Code']}"))
    
    return tests


def check_role_trust_policy(role_arn: str, current_identity: Dict) -> Tuple[bool, str]:
    """Check if current identity can assume the role based on trust policy."""
    try:
        # Extract role name from ARN (handle nested paths)
        role_path = role_arn.split(':role/')[-1]
        
        iam = boto3.client('iam')
        role = iam.get_role(RoleName=role_path)
        
        trust_policy = role['Role']['AssumeRolePolicyDocument']
        
        # Basic check - look for current account in trust policy
        current_account = current_identity['Account']
        trust_policy_str = json.dumps(trust_policy)
        
        if current_account in trust_policy_str:
            return True, f"✅ Trust policy allows access from account {current_account}"
        else:
            return False, f"❌ Trust policy may not allow access from account {current_account}"
            
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            return False, f"❌ Role {role_path} does not exist"
        else:
            return False, f"❌ Cannot check trust policy: {e.response['Error']['Code']}"


def main():
    # Load environment variables from .env file
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Validate AWS role ARN for JWT testing')
    parser.add_argument('--role-arn', help='Role ARN to validate (overrides QUILT_TEST_ROLE_ARN)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Get role ARN
    role_arn = args.role_arn or os.environ.get('QUILT_TEST_ROLE_ARN')
    
    if not role_arn:
        print("❌ No role ARN provided")
        print("   Set QUILT_TEST_ROLE_ARN environment variable or use --role-arn")
        print("   Example: export QUILT_TEST_ROLE_ARN=arn:aws:iam::123456789:role/QuiltMCPTestRole")
        return 1
    
    print(f"🔍 Validating role ARN: {role_arn}")
    print("=" * 80)
    
    # Step 1: Validate ARN format
    print("1. Validating ARN format...")
    valid_format, format_msg = validate_arn_format(role_arn)
    print(f"   {format_msg}")
    
    if not valid_format:
        return 1
    
    # Step 2: Check current AWS identity
    print("\n2. Checking current AWS identity...")
    has_identity, identity_msg, current_identity = get_current_identity()
    print(f"   {identity_msg}")
    
    if not has_identity:
        print("   💡 Configure AWS credentials with: aws configure")
        return 1
    
    # Step 3: Check trust policy (if possible)
    print("\n3. Checking role trust policy...")
    trust_ok, trust_msg = check_role_trust_policy(role_arn, current_identity)
    print(f"   {trust_msg}")
    
    # Step 4: Test role assumption
    print("\n4. Testing role assumption...")
    can_assume, assume_msg, credentials = test_role_assumption(role_arn)
    print(f"   {assume_msg}")
    
    if not can_assume:
        print("\n❌ VALIDATION FAILED: Cannot assume role")
        print("\n🔧 Troubleshooting:")
        print("   1. Verify role exists in the correct AWS account")
        print("   2. Check role trust policy allows your current identity")
        print("   3. Ensure your AWS credentials have sts:AssumeRole permission")
        print("   4. Try: aws sts assume-role --role-arn <ARN> --role-session-name test")
        return 1
    
    # Step 5: Test permissions with assumed role
    print("\n5. Testing permissions with assumed role...")
    permission_tests = test_role_permissions(credentials)
    
    all_passed = True
    for test_name, passed, message in permission_tests:
        status = "✅" if passed else "❌"
        print(f"   {status} {test_name}: {message}")
        if not passed:
            all_passed = False
    
    # Summary
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ VALIDATION PASSED: Role ARN is ready for JWT testing")
        print(f"   Role: {role_arn}")
        print("   The role can be assumed and has basic AWS permissions")
        print("\n💡 Next steps:")
        print("   1. Run: make test-stateless-mcp")
        print("   2. Check server logs for AWS role assumption")
        print("   3. Verify JWT claims include this role ARN")
    else:
        print("⚠️  VALIDATION PARTIAL: Role can be assumed but lacks some permissions")
        print("   This may cause some MCP tools to fail")
        print("\n🔧 Consider adding these permissions to the role:")
        print("   - S3: s3:ListBucket, s3:GetObject, s3:GetBucketLocation")
        print("   - IAM: iam:ListRoles, iam:GetRole")
        print("   - STS: sts:GetCallerIdentity (usually included)")
    
    return 0 if all_passed else 2


if __name__ == '__main__':
    sys.exit(main())