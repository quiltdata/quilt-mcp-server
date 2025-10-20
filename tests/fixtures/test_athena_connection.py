#!/usr/bin/env python3
"""
Test script to isolate and debug Athena connection setup
"""

import os
import sys
import logging

import pytest

# Add app to Python path
sys.path.insert(0, "app")

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def test_quilt3_session():
    """Test quilt3 session and credential access"""
    print("=" * 60)
    print("Testing quilt3 session and credentials")
    print("=" * 60)

    try:
        import quilt3

        print("✅ quilt3 imported successfully")

        # Test botocore session
        botocore_session = quilt3.session.create_botocore_session()
        print("✅ Botocore session created")

        # Get credentials
        credentials = botocore_session.get_credentials()
        print(f"✅ Credentials obtained: {type(credentials)}")

        # Get region
        region = botocore_session.get_config_variable("region")
        print(f"✅ Region: {region}")

        # Test credential attributes
        print(f"   Access key: {credentials.access_key[:10]}...")
        print(f"   Secret key: {credentials.secret_key[:10]}...")
        print(f"   Token: {'Yes' if credentials.token else 'No'}")

        return botocore_session, credentials, region

    except Exception as e:
        print(f"❌ Error with quilt3 session: {e}")
        return None, None, None


def test_athena_service_creation():
    """Test AthenaQueryService creation"""
    print("\n" + "=" * 60)
    print("Testing AthenaQueryService creation")
    print("=" * 60)

    try:
        from quilt_mcp.services.athena_service import AthenaQueryService

        print("✅ AthenaQueryService imported successfully")

        # Test service creation
        service = AthenaQueryService(use_quilt_auth=True)
        print("✅ AthenaQueryService created")

        return service

    except Exception as e:
        print(f"❌ Error creating AthenaQueryService: {e}")
        import traceback

        traceback.print_exc()
        return None


def check_sqlalchemy_engine_creation(service):
    """Test SQLAlchemy engine creation"""
    print("\n" + "=" * 60)
    print("Testing SQLAlchemy engine creation")
    print("=" * 60)

    if not service:
        print("❌ No service available")
        return None

    try:
        # Test engine creation (this calls _create_sqlalchemy_engine)
        engine = service.engine
        print(f"✅ SQLAlchemy engine created: {engine}")
        print(f"   Engine URL: {engine.url}")

        return engine

    except Exception as e:
        print(f"❌ Error creating SQLAlchemy engine: {e}")
        import traceback

        traceback.print_exc()
        return None


def check_engine_connection(engine):
    """Test actual connection to Athena"""
    print("\n" + "=" * 60)
    print("Testing engine connection to Athena")
    print("=" * 60)

    if not engine:
        print("❌ No engine available")
        return False

    try:
        with engine.connect() as conn:
            print("✅ Successfully connected to Athena")

            # Try a simple query
            from sqlalchemy import text

            result = conn.execute(text("SELECT 1 as test_value"))
            row = result.fetchone()
            print(f"✅ Simple query successful: {row}")

        return True

    except Exception as e:
        print(f"❌ Error connecting to Athena: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_glue_client(service):
    """Test Glue client creation and basic operation"""
    print("\n" + "=" * 60)
    print("Testing Glue client")
    print("=" * 60)

    if not service:
        print("❌ No service available")
        return False

    try:
        glue_client = service.glue_client
        print("✅ Glue client created")

        # Try listing databases
        response = glue_client.get_databases()
        databases = response.get("DatabaseList", [])
        print(f"✅ Listed {len(databases)} databases")

        for db in databases[:3]:  # Show first 3 databases
            print(f"   - {db.get('Name', 'Unknown')}")

        return True

    except Exception as e:
        print(f"❌ Error with Glue client: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_mcp_tools():
    """Test MCP tool functions directly"""
    print("\n" + "=" * 60)
    print("Testing MCP tools directly")
    print("=" * 60)

    try:
        from quilt_mcp.services.athena_read_service import (
            athena_databases_list,
            athena_query_validate,
        )

        print("✅ Athena tools imported successfully")

        # Test query validation (doesn't need AWS)
        result = athena_query_validate("SELECT 1 as test")
        print(f"✅ Query validation: {result.get('valid', False)}")

        # Test database listing
        result = athena_databases_list()
        if result.get("success"):
            print(f"✅ Database listing successful: {result.get('count', 0)} databases")
        else:
            print(f"❌ Database listing failed: {result.get('error', 'Unknown error')}")

        # Test workgroups listing
        from quilt_mcp.services.athena_read_service import athena_workgroups_list

        workgroups_result = athena_workgroups_list()
        if workgroups_result.get("success"):
            total = workgroups_result.get("count", 0)
            print(f"✅ Workgroups listing successful: {total} workgroups found")

            # Show the top few workgroups (Episodes 2-3: no 'accessible' or 'state' fields)
            for wg in workgroups_result.get("workgroups", [])[:3]:
                name = wg.get('name', 'Unknown')
                description = wg.get('description', 'No description')
                print(f"   ✅ {name} - {description}")
        else:
            error_msg = workgroups_result.get('error', 'Unknown error')
            print(f"❌ Workgroups listing failed: {error_msg}")

        return result.get("success", False) and workgroups_result.get("success", False)

    except Exception as e:
        print(f"❌ Error with MCP tools: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main test function"""
    print("🧪 Athena Connection Test Script")
    print("This script will test each component of the Athena connection setup\n")

    # Test 1: quilt3 session
    botocore_session, credentials, region = test_quilt3_session()

    # Test 2: Service creation
    service = test_athena_service_creation()

    # Test 3: Engine creation
    engine = check_sqlalchemy_engine_creation(service)

    # Test 4: Actual connection
    connection_success = check_engine_connection(engine)

    # Test 5: Glue client
    glue_success = check_glue_client(service)

    # Test 6: MCP tools
    mcp_success = test_mcp_tools()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"quilt3 session:     {'✅' if credentials else '❌'}")
    print(f"Service creation:   {'✅' if service else '❌'}")
    print(f"Engine creation:    {'✅' if engine else '❌'}")
    print(f"Athena connection:  {'✅' if connection_success else '❌'}")
    print(f"Glue client:        {'✅' if glue_success else '❌'}")
    print(f"MCP tools:          {'✅' if mcp_success else '❌'}")

    if all([credentials, service, engine, connection_success, glue_success, mcp_success]):
        print("\n🎉 All tests passed! Athena integration is working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
