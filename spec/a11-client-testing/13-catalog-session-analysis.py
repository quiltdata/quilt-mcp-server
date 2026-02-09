#!/usr/bin/env python3
"""
Analyze what a real Quilt catalog session contains.

This script examines the current authenticated session to understand
what information is needed for catalog authentication.
"""

import os
import sys
import json

sys.path.insert(0, 'src')


def analyze_quilt_session():
    """Analyze the current quilt3 session."""
    print("🔍 Analyzing Current Quilt Catalog Session")
    print("=" * 60)

    try:
        import quilt3
        from quilt_mcp.services.quilt_service import QuiltService

        qs = QuiltService()

        # Get basic session info
        print("📊 Basic Session Information:")
        print(f"  Logged in: {qs.is_authenticated()}")
        print(f"  Logged in URL: {qs.get_logged_in_url()}")
        print(f"  Registry URL: {qs.get_registry_url()}")

        # Get full catalog info
        catalog_info = qs.get_catalog_info()
        print(f"\n📋 Full Catalog Info:")
        for key, value in catalog_info.items():
            print(f"  {key}: {value}")

        # Check if we can get the session object
        if qs.has_session_support():
            print(f"\n🔧 Session Support Available")
            try:
                session = qs.get_session()
                print(f"  Session type: {type(session)}")
                print(f"  Session headers: {getattr(session, 'headers', 'N/A')}")

                # Check if session has authentication info
                if hasattr(session, 'auth'):
                    print(f"  Session auth: {session.auth}")
                if hasattr(session, 'cookies'):
                    print(f"  Session cookies: {len(session.cookies)} cookies")

            except Exception as e:
                print(f"  ❌ Error getting session: {e}")

        # Check quilt3 config
        print(f"\n⚙️  Quilt3 Configuration:")
        try:
            config = quilt3.config()
            if config:
                for key, value in config.items():
                    if 'token' in key.lower() or 'secret' in key.lower():
                        print(f"  {key}: [REDACTED]")
                    else:
                        print(f"  {key}: {value}")
            else:
                print("  No config available")
        except Exception as e:
            print(f"  ❌ Error getting config: {e}")

        # Check for credential files
        print(f"\n📁 Credential Files:")
        quilt_dir = os.path.expanduser("~/.quilt")
        if os.path.exists(quilt_dir):
            print(f"  ~/.quilt directory exists")
            for file in os.listdir(quilt_dir):
                file_path = os.path.join(quilt_dir, file)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    print(f"    {file}: {size} bytes")

                    # Try to read config files (but redact sensitive info)
                    if file in ['config.json', 'credentials.json']:
                        try:
                            with open(file_path, 'r') as f:
                                data = json.load(f)
                            print(f"      Content keys: {list(data.keys())}")

                            # Show non-sensitive parts
                            for key, value in data.items():
                                if any(
                                    sensitive in key.lower() for sensitive in ['token', 'secret', 'key', 'password']
                                ):
                                    print(f"        {key}: [REDACTED]")
                                else:
                                    print(f"        {key}: {value}")
                        except Exception as e:
                            print(f"      ❌ Error reading {file}: {e}")
        else:
            print(f"  ~/.quilt directory does not exist")

    except Exception as e:
        print(f"❌ ERROR analyzing session: {e}")
        import traceback

        traceback.print_exc()


def check_catalog_api_access():
    """Check what API calls are made to the catalog."""
    print(f"\n🌐 Catalog API Access Analysis")
    print("=" * 60)

    try:
        from quilt_mcp.services.quilt_service import QuiltService

        qs = QuiltService()

        if qs.has_session_support():
            session = qs.get_session()
            registry_url = qs.get_registry_url()

            print(f"Registry URL: {registry_url}")

            # Try a simple GraphQL query to see what authentication is used
            if registry_url:
                graphql_url = f"{registry_url.rstrip('/')}/graphql"
                print(f"GraphQL URL: {graphql_url}")

                # Simple query to list bucket configs
                query = {"query": "{ bucketConfigs { name } }"}

                print(f"\n🔍 Testing GraphQL Query:")
                print(f"  Query: {query}")

                try:
                    response = session.post(graphql_url, json=query, timeout=10)
                    print(f"  Status: {response.status_code}")
                    print(f"  Headers sent: {dict(response.request.headers)}")

                    if response.status_code == 200:
                        data = response.json()
                        bucket_configs = data.get('data', {}).get('bucketConfigs', [])
                        print(f"  Buckets found: {len(bucket_configs)}")
                        if bucket_configs:
                            print(f"  First bucket: {bucket_configs[0].get('name', 'N/A')}")
                    else:
                        print(f"  Error response: {response.text[:200]}")

                except Exception as e:
                    print(f"  ❌ GraphQL query failed: {e}")

    except Exception as e:
        print(f"❌ ERROR checking API access: {e}")


def analyze_jwt_requirements():
    """Analyze what a JWT would need to contain for catalog access."""
    print(f"\n🎫 JWT Requirements Analysis")
    print("=" * 60)

    print("Based on the session analysis, a JWT for catalog access would need:")
    print("1. 🔐 Authentication mechanism (how to prove identity to catalog)")
    print("2. 🌐 Catalog URL (which catalog to authenticate with)")
    print("3. 🎯 User identity (who is making the request)")
    print("4. ⏰ Expiration (when the authentication expires)")
    print("5. 🔑 Authorization info (what permissions the user has)")

    print(f"\nCurrent JWT contains:")
    print("✅ AWS role ARN (for AWS access)")
    print("✅ User identity (sub claim)")
    print("✅ Expiration (exp claim)")
    print("❌ Catalog authentication mechanism")
    print("❌ Catalog URL")
    print("❌ Catalog authorization info")

    print(f"\nPossible solutions:")
    print("1. 🎫 Include catalog bearer token in JWT")
    print("2. 🔐 Include catalog credentials in JWT")
    print("3. 🌐 Use AWS credentials to authenticate with catalog")
    print("4. 🔄 Perform programmatic catalog login using AWS role")


def main():
    """Main analysis function."""
    print("🔍 Catalog Session Analysis")
    print("Understanding what's needed for catalog authentication in JWTs")
    print("=" * 80)

    analyze_quilt_session()
    check_catalog_api_access()
    analyze_jwt_requirements()

    print("\n" + "=" * 80)
    print("📋 CONCLUSION:")
    print("This analysis will show whether:")
    print("1. Current session uses bearer tokens, cookies, or other auth")
    print("2. What information is needed to recreate catalog access")
    print("3. How to modify JWT generation to include catalog auth")
    print("4. Whether the issue is JWT content or architecture")


if __name__ == "__main__":
    main()
