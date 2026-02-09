# Test Infrastructure Setup Guide: QuiltOps E2E Tests

**Version:** 1.0
**Date:** 2026-02-05
**Status:** Design Specification
**Companion to:** 01-quilt-ops-e2e-spec.md

## Executive Summary

This document provides detailed specifications for setting up the test infrastructure required for QuiltOps e2e tests. It covers AWS resource provisioning, test data generation, authentication configuration, and CI/CD integration.

**Key Deliverables:**
- AWS CloudFormation/Terraform templates
- Test data generation scripts
- Authentication setup automation
- CI/CD workflow configuration
- Cost monitoring and cleanup automation

---

## 1. AWS Infrastructure

### 1.1 S3 Buckets

#### Bucket: quilt-mcp-test-data

**Purpose:** Immutable reference data for tests

**Configuration:**
```yaml
BucketName: quilt-mcp-test-data
Region: us-east-1
Versioning: Enabled
Encryption: AES256
LifecyclePolicy:
  - Id: DeleteOldVersions
    Status: Enabled
    NoncurrentVersionExpiration:
      Days: 7
PublicAccessBlock:
  BlockPublicAcls: true
  IgnorePublicAcls: true
  BlockPublicPolicy: true
  RestrictPublicBuckets: true
Tags:
  - Key: Purpose
    Value: QuiltMCP-E2E-Testing
  - Key: DataType
    Value: Reference
  - Key: Mutable
    Value: false
```

**Access Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowTestRoleReadAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:role/quilt-mcp-test-role"
      },
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:ListBucket",
        "s3:ListBucketVersions"
      ],
      "Resource": [
        "arn:aws:s3:::quilt-mcp-test-data",
        "arn:aws:s3:::quilt-mcp-test-data/*"
      ]
    }
  ]
}
```

**Structure:**
```
quilt-mcp-test-data/
├── simple-csv/
│   ├── file1.csv (100 KB)
│   ├── file2.csv (100 KB)
│   ├── file3.csv (100 KB)
│   ├── file4.csv (100 KB)
│   └── file5.csv (100 KB)
├── nested-structure/
│   ├── data/
│   │   ├── raw/
│   │   │   ├── 2024-01/
│   │   │   │   ├── data_001.csv (200 KB)
│   │   │   │   └── data_002.csv (200 KB)
│   │   │   └── 2024-02/
│   │   │       ├── data_003.csv (200 KB)
│   │   │       └── data_004.csv (200 KB)
│   │   └── processed/
│   │       ├── summary.json (50 KB)
│   │       └── aggregated.parquet (500 KB)
│   └── metadata/
│       ├── schema.json (10 KB)
│       └── README.md (5 KB)
├── large-package/
│   ├── chunk_000.bin to chunk_099.bin (5 MB each = 500 MB total)
├── mixed-formats/
│   ├── data.json (1 MB)
│   ├── data.csv (2 MB)
│   ├── data.parquet (5 MB)
│   ├── data.arrow (5 MB)
│   ├── image.png (500 KB)
│   ├── image.jpg (500 KB)
│   └── document.pdf (1 MB)
├── versioned-data/
│   ├── v1/
│   │   ├── file1.csv (1 MB)
│   │   ├── file2.csv (1 MB)
│   │   └── file3.csv (1 MB)
│   └── v2/
│       ├── file1.csv (1.1 MB - modified)
│       ├── file2.csv (1 MB - unchanged)
│       ├── file3.csv (1 MB - unchanged)
│       └── file4.csv (1 MB - new)
├── metadata-rich/
│   ├── data/
│   │   └── ... (10 files, 5 MB total)
│   └── quilt_metadata.json (complex metadata)
├── empty-package/
│   └── quilt_metadata.json (metadata only)
├── single-file/
│   └── data.csv (100 KB)
└── checksums.json (file integrity validation)
```

#### Bucket: quilt-mcp-test-scratch

**Purpose:** Ephemeral workspace for test operations

**Configuration:**
```yaml
BucketName: quilt-mcp-test-scratch
Region: us-east-1
Versioning: Disabled
Encryption: AES256
LifecyclePolicy:
  - Id: AutoDeleteOldObjects
    Status: Enabled
    Expiration:
      Days: 1  # Auto-delete after 24 hours
  - Id: AbortIncompleteMultipartUpload
    Status: Enabled
    AbortIncompleteMultipartUpload:
      DaysAfterInitiation: 1
PublicAccessBlock:
  BlockPublicAcls: true
  IgnorePublicAcls: true
  BlockPublicPolicy: true
  RestrictPublicBuckets: true
Tags:
  - Key: Purpose
    Value: QuiltMCP-E2E-Testing
  - Key: DataType
    Value: Scratch
  - Key: Mutable
    Value: true
```

**Access Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowTestRoleFullAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:role/quilt-mcp-test-role"
      },
      "Action": [
        "s3:*"
      ],
      "Resource": [
        "arn:aws:s3:::quilt-mcp-test-scratch",
        "arn:aws:s3:::quilt-mcp-test-scratch/*"
      ]
    }
  ]
}
```

#### Bucket: quilt-mcp-test-packages

**Purpose:** Package registry for test packages

**Configuration:**
```yaml
BucketName: quilt-mcp-test-packages
Region: us-east-1
Versioning: Enabled
Encryption: AES256
LifecyclePolicy:
  - Id: DeleteOldPackageVersions
    Status: Enabled
    NoncurrentVersionExpiration:
      Days: 30  # Keep package history for 30 days
PublicAccessBlock:
  BlockPublicAcls: true
  IgnorePublicAcls: true
  BlockPublicPolicy: true
  RestrictPublicBuckets: true
Tags:
  - Key: Purpose
    Value: QuiltMCP-E2E-Testing
  - Key: DataType
    Value: PackageRegistry
  - Key: Mutable
    Value: true
```

**Access Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowTestRoleFullAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:role/quilt-mcp-test-role"
      },
      "Action": [
        "s3:*"
      ],
      "Resource": [
        "arn:aws:s3:::quilt-mcp-test-packages",
        "arn:aws:s3:::quilt-mcp-test-packages/*"
      ]
    }
  ]
}
```

### 1.2 IAM Role and Policy

#### IAM Role: quilt-mcp-test-role

**Trust Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com",
        "AWS": "arn:aws:iam::ACCOUNT_ID:user/ci-runner"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**Inline Policy: QuiltMCPTestAccess**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3BucketAccess",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:GetBucketVersioning",
        "s3:GetBucketTagging"
      ],
      "Resource": [
        "arn:aws:s3:::quilt-mcp-test-data",
        "arn:aws:s3:::quilt-mcp-test-scratch",
        "arn:aws:s3:::quilt-mcp-test-packages"
      ]
    },
    {
      "Sid": "S3ObjectAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:GetObjectTagging",
        "s3:PutObject",
        "s3:PutObjectTagging",
        "s3:DeleteObject",
        "s3:DeleteObjectVersion"
      ],
      "Resource": [
        "arn:aws:s3:::quilt-mcp-test-data/*",
        "arn:aws:s3:::quilt-mcp-test-scratch/*",
        "arn:aws:s3:::quilt-mcp-test-packages/*"
      ]
    },
    {
      "Sid": "AthenaAccess",
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:StopQueryExecution",
        "athena:ListDatabases",
        "athena:ListTableMetadata"
      ],
      "Resource": "*"
    },
    {
      "Sid": "GlueAccess",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetTable",
        "glue:GetPartitions",
        "glue:CreateTable",
        "glue:UpdateTable",
        "glue:DeleteTable"
      ],
      "Resource": "*"
    }
  ]
}
```

### 1.3 Athena Configuration (Tabulator)

#### Glue Data Catalog: quilt_test_catalog

**Database: quilt_mcp_test_db**
```yaml
Name: quilt_mcp_test_db
Description: Test database for Tabulator operations
Location: s3://quilt-mcp-test-data/athena/
```

**Sample Table: test_table_1**
```sql
CREATE EXTERNAL TABLE quilt_mcp_test_db.test_table_1 (
  id INT,
  name STRING,
  value DOUBLE,
  timestamp TIMESTAMP
)
STORED AS PARQUET
LOCATION 's3://quilt-mcp-test-data/athena/test_table_1/';
```

#### Athena Workgroup: quilt-mcp-test-workgroup

**Configuration:**
```yaml
Name: quilt-mcp-test-workgroup
Description: Workgroup for QuiltMCP e2e tests
ResultConfiguration:
  OutputLocation: s3://quilt-mcp-test-scratch/athena-results/
  EncryptionConfiguration:
    EncryptionOption: SSE_S3
EnforceWorkGroupConfiguration: true
PublishCloudWatchMetricsEnabled: true
Tags:
  - Key: Purpose
    Value: QuiltMCP-E2E-Testing
```

### 1.4 Quilt Catalog Instance (Multiuser Mode)

**Catalog URL:** `https://test-catalog.quiltdata.com`

**Configuration:**
- **GraphQL Endpoint:** `https://api.test-catalog.quiltdata.com/graphql`
- **Registry Bucket:** `s3://quilt-mcp-test-packages`
- **Analytics Bucket:** `s3://quilt-mcp-test-data`
- **Admin API:** Enabled
- **Authentication:** JWT tokens + local sessions

**Pre-configured Users:**

| Username | Email | Role | Admin | Password |
|----------|-------|------|-------|----------|
| test-admin | admin@test.com | admin | Yes | (Generated) |
| test-user | user@test.com | user | No | (Generated) |
| test-readonly | readonly@test.com | viewer | No | (Generated) |
| test-service | service@test.com | service | No | (Generated) |

**Setup Command:**
```bash
# Create users via admin GraphQL mutations
uv run python tests/e2e/fixtures/setup_catalog_users.py
```

### 1.5 Cost Monitoring

**CloudWatch Billing Alarm:**
```yaml
AlarmName: QuiltMCP-E2E-Tests-Cost-Alert
MetricName: EstimatedCharges
Namespace: AWS/Billing
Statistic: Maximum
Period: 86400  # 24 hours
EvaluationPeriods: 1
Threshold: 10.0  # Alert if costs exceed $10/day
ComparisonOperator: GreaterThanThreshold
TreatMissingData: notBreaching
AlarmActions:
  - arn:aws:sns:us-east-1:ACCOUNT_ID:quilt-mcp-alerts
```

**Daily Cost Report:**
```bash
# Automated script: tests/e2e/fixtures/cost_report.sh
#!/bin/bash
# Reports daily costs for test resources

aws ce get-cost-and-usage \
  --time-period Start=$(date -d '1 day ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --filter file://test-resource-filter.json
```

---

## 2. Test Data Generation

### 2.1 Data Generation Script

**Location:** `tests/e2e/fixtures/generate_test_data.py`

**Requirements:**
- Deterministic (seeded random generation)
- Versioned (track data schema changes)
- Validated (checksums for integrity)
- Documented (README per dataset)
- Idempotent (safe to re-run)

**Script Structure:**
```python
#!/usr/bin/env python3
"""
generate_test_data.py - Generate deterministic test datasets

Creates reference test data for QuiltOps e2e tests.
All data generation is seeded for reproducibility.
"""

import os
import json
import hashlib
import random
from pathlib import Path
from typing import Dict, Any
import pandas as pd
import numpy as np
from PIL import Image


# Configuration
DATA_VERSION = "1.0.0"
RANDOM_SEED = 42
OUTPUT_DIR = Path(__file__).parent / "data"

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


class TestDataGenerator:
    """Generate deterministic test datasets"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.checksums: Dict[str, str] = {}

    def generate_all(self):
        """Generate all test datasets"""
        print("Generating test data...")

        self.generate_simple_csv()
        self.generate_nested_structure()
        self.generate_large_package()
        self.generate_mixed_formats()
        self.generate_versioned_data()
        self.generate_metadata_rich()
        self.generate_empty_package()
        self.generate_single_file()

        self.write_checksums()
        self.write_manifest()

        print(f"✓ Test data generated in {self.output_dir}")

    def generate_simple_csv(self):
        """Generate 5 simple CSV files (1 MB total)"""
        dataset_dir = self.output_dir / "simple-csv"
        dataset_dir.mkdir(parents=True, exist_ok=True)

        for i in range(1, 6):
            df = pd.DataFrame({
                'id': range(1000),
                'name': [f'name_{j:04d}' for j in range(1000)],
                'value': np.random.randn(1000),
                'category': np.random.choice(['A', 'B', 'C'], 1000),
                'timestamp': pd.date_range('2024-01-01', periods=1000, freq='H')
            })

            filepath = dataset_dir / f"file{i}.csv"
            df.to_csv(filepath, index=False)
            self._record_checksum(filepath)

        print(f"  ✓ simple-csv: 5 files")

    def generate_nested_structure(self):
        """Generate nested directory structure (10 MB total, 50 files)"""
        dataset_dir = self.output_dir / "nested-structure"

        # Create directory structure
        (dataset_dir / "data" / "raw" / "2024-01").mkdir(parents=True, exist_ok=True)
        (dataset_dir / "data" / "raw" / "2024-02").mkdir(parents=True, exist_ok=True)
        (dataset_dir / "data" / "processed").mkdir(parents=True, exist_ok=True)
        (dataset_dir / "metadata").mkdir(parents=True, exist_ok=True)

        # Generate raw data files
        for month in ["2024-01", "2024-02"]:
            for i in range(10):
                df = pd.DataFrame({
                    'id': range(2000),
                    'measurement': np.random.randn(2000),
                    'sensor': np.random.choice(['sensor1', 'sensor2', 'sensor3'], 2000)
                })
                filepath = dataset_dir / "data" / "raw" / month / f"data_{i:03d}.csv"
                df.to_csv(filepath, index=False)
                self._record_checksum(filepath)

        # Generate processed data
        summary = {"total_files": 20, "date_range": ["2024-01", "2024-02"]}
        filepath = dataset_dir / "data" / "processed" / "summary.json"
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        self._record_checksum(filepath)

        # Generate metadata
        schema = {
            "version": "1.0",
            "fields": [
                {"name": "id", "type": "integer"},
                {"name": "measurement", "type": "float"},
                {"name": "sensor", "type": "string"}
            ]
        }
        filepath = dataset_dir / "metadata" / "schema.json"
        with open(filepath, 'w') as f:
            json.dump(schema, f, indent=2)
        self._record_checksum(filepath)

        # README
        readme = """# Nested Structure Dataset

This dataset demonstrates nested directory structures.

## Structure:
- data/raw/YYYY-MM/ - Raw sensor data by month
- data/processed/ - Aggregated results
- metadata/ - Schema and documentation
"""
        filepath = dataset_dir / "metadata" / "README.md"
        with open(filepath, 'w') as f:
            f.write(readme)
        self._record_checksum(filepath)

        print(f"  ✓ nested-structure: 23 files in nested dirs")

    def generate_large_package(self):
        """Generate large package (500 MB, 100 files)"""
        dataset_dir = self.output_dir / "large-package"
        dataset_dir.mkdir(parents=True, exist_ok=True)

        # Generate 100 x 5MB binary files
        for i in range(100):
            filepath = dataset_dir / f"chunk_{i:03d}.bin"

            # Generate 5MB of deterministic random data
            data = np.random.bytes(5 * 1024 * 1024)
            with open(filepath, 'wb') as f:
                f.write(data)
            self._record_checksum(filepath)

        print(f"  ✓ large-package: 100 files (500 MB)")

    def generate_mixed_formats(self):
        """Generate mixed file formats (50 MB total)"""
        dataset_dir = self.output_dir / "mixed-formats"
        dataset_dir.mkdir(parents=True, exist_ok=True)

        # JSON
        data_json = {
            "records": [
                {"id": i, "name": f"record_{i}", "value": random.random()}
                for i in range(10000)
            ]
        }
        filepath = dataset_dir / "data.json"
        with open(filepath, 'w') as f:
            json.dump(data_json, f)
        self._record_checksum(filepath)

        # CSV
        df_csv = pd.DataFrame({
            'id': range(20000),
            'name': [f'name_{i:05d}' for i in range(20000)],
            'value': np.random.randn(20000)
        })
        filepath = dataset_dir / "data.csv"
        df_csv.to_csv(filepath, index=False)
        self._record_checksum(filepath)

        # Parquet
        df_parquet = pd.DataFrame({
            'id': range(50000),
            'value1': np.random.randn(50000),
            'value2': np.random.randn(50000),
            'category': np.random.choice(['X', 'Y', 'Z'], 50000)
        })
        filepath = dataset_dir / "data.parquet"
        df_parquet.to_parquet(filepath)
        self._record_checksum(filepath)

        # PNG image
        img_png = Image.new('RGB', (1000, 1000), color=(73, 109, 137))
        filepath = dataset_dir / "image.png"
        img_png.save(filepath)
        self._record_checksum(filepath)

        # JPEG image
        img_jpg = Image.new('RGB', (1000, 1000), color=(255, 200, 100))
        filepath = dataset_dir / "image.jpg"
        img_jpg.save(filepath, quality=85)
        self._record_checksum(filepath)

        print(f"  ✓ mixed-formats: 5 files (JSON, CSV, Parquet, PNG, JPG)")

    def generate_versioned_data(self):
        """Generate two versions of data for diff testing (20 MB total)"""
        dataset_dir = self.output_dir / "versioned-data"

        # Version 1
        v1_dir = dataset_dir / "v1"
        v1_dir.mkdir(parents=True, exist_ok=True)

        for i in range(1, 4):
            df = pd.DataFrame({
                'id': range(10000),
                'value': np.random.randn(10000) + i  # Seeded differently
            })
            filepath = v1_dir / f"file{i}.csv"
            df.to_csv(filepath, index=False)
            self._record_checksum(filepath)

        # Version 2 (modified file1, added file4)
        v2_dir = dataset_dir / "v2"
        v2_dir.mkdir(parents=True, exist_ok=True)

        # Modified file1
        df1 = pd.DataFrame({
            'id': range(11000),  # More rows
            'value': np.random.randn(11000) + 1.5
        })
        filepath = v2_dir / "file1.csv"
        df1.to_csv(filepath, index=False)
        self._record_checksum(filepath)

        # Unchanged files 2 and 3 (copy from v1)
        for i in [2, 3]:
            import shutil
            shutil.copy(v1_dir / f"file{i}.csv", v2_dir / f"file{i}.csv")
            self._record_checksum(v2_dir / f"file{i}.csv")

        # New file4
        df4 = pd.DataFrame({
            'id': range(10000),
            'value': np.random.randn(10000) + 4
        })
        filepath = v2_dir / "file4.csv"
        df4.to_csv(filepath, index=False)
        self._record_checksum(filepath)

        print(f"  ✓ versioned-data: v1 (3 files), v2 (4 files)")

    def generate_metadata_rich(self):
        """Generate package with complex metadata (5 MB)"""
        dataset_dir = self.output_dir / "metadata-rich"
        data_dir = dataset_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        # Generate data files
        for i in range(10):
            df = pd.DataFrame({
                'id': range(5000),
                'value': np.random.randn(5000)
            })
            filepath = data_dir / f"data_{i:02d}.csv"
            df.to_csv(filepath, index=False)
            self._record_checksum(filepath)

        # Generate complex metadata
        metadata = {
            "version": "2.1.0",
            "description": "Metadata-rich test dataset",
            "tags": ["test", "e2e", "metadata", "complex"],
            "authors": [
                {"name": "Test User", "email": "test@example.com"},
                {"name": "Test Admin", "email": "admin@example.com"}
            ],
            "license": "MIT",
            "created": "2024-01-01T00:00:00Z",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "integer",
                        "description": "Unique identifier",
                        "constraints": {"minimum": 0}
                    },
                    {
                        "name": "value",
                        "type": "float",
                        "description": "Measurement value",
                        "unit": "meters"
                    }
                ]
            },
            "provenance": {
                "source": "Generated for testing",
                "method": "Deterministic random generation",
                "seed": RANDOM_SEED
            },
            "custom_fields": {
                "experiment_id": "EXP-001",
                "instrument": "TestInstrument-3000",
                "calibration_date": "2024-01-01"
            }
        }

        filepath = dataset_dir / "quilt_metadata.json"
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2)
        self._record_checksum(filepath)

        print(f"  ✓ metadata-rich: 10 files + complex metadata")

    def generate_empty_package(self):
        """Generate empty package (metadata only)"""
        dataset_dir = self.output_dir / "empty-package"
        dataset_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "version": "1.0.0",
            "description": "Empty package for edge case testing",
            "tags": ["test", "empty", "edge-case"],
            "note": "This package intentionally contains no data files"
        }

        filepath = dataset_dir / "quilt_metadata.json"
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2)
        self._record_checksum(filepath)

        print(f"  ✓ empty-package: metadata only (no data files)")

    def generate_single_file(self):
        """Generate minimal single-file package (100 KB)"""
        dataset_dir = self.output_dir / "single-file"
        dataset_dir.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame({
            'id': range(1000),
            'value': np.random.randn(1000)
        })

        filepath = dataset_dir / "data.csv"
        df.to_csv(filepath, index=False)
        self._record_checksum(filepath)

        print(f"  ✓ single-file: 1 file (100 KB)")

    def _record_checksum(self, filepath: Path):
        """Calculate and record file checksum"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        relative_path = filepath.relative_to(self.output_dir)
        self.checksums[str(relative_path)] = sha256_hash.hexdigest()

    def write_checksums(self):
        """Write checksums.json file"""
        filepath = self.output_dir / "checksums.json"
        with open(filepath, 'w') as f:
            json.dump(self.checksums, f, indent=2, sort_keys=True)
        print(f"  ✓ checksums.json: {len(self.checksums)} files")

    def write_manifest(self):
        """Write manifest.json with dataset metadata"""
        manifest = {
            "version": DATA_VERSION,
            "generated": "2024-01-01T00:00:00Z",
            "seed": RANDOM_SEED,
            "datasets": {
                "simple-csv": {"files": 5, "size_mb": 1},
                "nested-structure": {"files": 23, "size_mb": 10},
                "large-package": {"files": 100, "size_mb": 500},
                "mixed-formats": {"files": 5, "size_mb": 50},
                "versioned-data": {"files": 7, "size_mb": 20},
                "metadata-rich": {"files": 11, "size_mb": 5},
                "empty-package": {"files": 1, "size_mb": 0},
                "single-file": {"files": 1, "size_mb": 0.1}
            },
            "total_files": len(self.checksums),
            "total_size_mb": 586.1
        }

        filepath = self.output_dir / "manifest.json"
        with open(filepath, 'w') as f:
            json.dump(manifest, f, indent=2)
        print(f"  ✓ manifest.json")


def main():
    generator = TestDataGenerator(OUTPUT_DIR)
    generator.generate_all()


if __name__ == "__main__":
    main()
```

**Usage:**
```bash
# Generate test data locally
uv run python tests/e2e/fixtures/generate_test_data.py

# Upload to S3
aws s3 sync tests/e2e/fixtures/data/ s3://quilt-mcp-test-data/ \
  --delete \
  --exclude ".*" \
  --profile quilt-mcp-tests
```

### 2.2 Baseline Package Creation

**Location:** `tests/e2e/fixtures/create_baseline_packages.py`

**Script Structure:**
```python
#!/usr/bin/env python3
"""
create_baseline_packages.py - Create baseline test packages

Uses generated test data to create packages in the test registry.
"""

import os
from pathlib import Path
from quilt_mcp.ops.factory import QuiltOpsFactory


class BaselinePackageCreator:
    """Create baseline packages for e2e tests"""

    def __init__(self, registry_url: str, data_bucket: str):
        self.ops = QuiltOpsFactory.create()
        self.registry_url = registry_url
        self.data_bucket = data_bucket

    def create_all(self):
        """Create all baseline packages"""
        print("Creating baseline packages...")

        self.create_simple_csv_package()
        self.create_nested_structure_package()
        self.create_large_package()
        self.create_mixed_formats_package()
        self.create_versioned_data_packages()
        self.create_metadata_rich_package()
        self.create_empty_package()
        self.create_single_file_package()

        print("✓ All baseline packages created")

    def create_simple_csv_package(self):
        """Create test-user/simple-csv package"""
        entries = [
            {
                "logical_key": f"file{i}.csv",
                "physical_key": f"s3://{self.data_bucket}/simple-csv/file{i}.csv"
            }
            for i in range(1, 6)
        ]

        result = self.ops.create_package_revision(
            package_name="test-user/simple-csv",
            registry=self.registry_url,
            entries=entries,
            message="Baseline: Simple CSV package",
            metadata={
                "description": "5 simple CSV files for basic testing",
                "tags": ["test", "csv", "baseline"]
            }
        )

        print(f"  ✓ test-user/simple-csv: {result.top_hash[:8]}")

    # ... (similar methods for other packages)


def main():
    registry_url = os.getenv("QUILT_TEST_REGISTRY_URL", "s3://quilt-mcp-test-packages")
    data_bucket = os.getenv("QUILT_TEST_BUCKET_DATA", "quilt-mcp-test-data")

    creator = BaselinePackageCreator(registry_url, data_bucket)
    creator.create_all()


if __name__ == "__main__":
    main()
```

**Usage:**
```bash
# Create baseline packages (local mode)
QUILT_MULTIUSER_MODE=false uv run python tests/e2e/fixtures/create_baseline_packages.py

# Create baseline packages (multiuser mode)
QUILT_MULTIUSER_MODE=true uv run python tests/e2e/fixtures/create_baseline_packages.py
```

---

## 3. Authentication Setup

### 3.1 Local Mode (Quilt3_Backend)

**Setup Steps:**
```bash
# Install quilt3 CLI (if not already installed)
pip install quilt3

# Configure local session
quilt3 login s3://quilt-mcp-test-packages

# Verify authentication
quilt3 whoami
# Should show: Authenticated to s3://quilt-mcp-test-packages
```

**Session Storage:**
```
~/.config/quilt/
├── config.json
└── session_cache/
    └── quilt-mcp-test-packages/
        └── credentials.json
```

### 3.2 Multiuser Mode (Platform_Backend)

**Setup Steps:**
```bash
# 1. Login to test catalog via web UI
open https://test-catalog.quiltdata.com

# 2. Copy JWT token from browser (DevTools > Application > Cookies)

# 3. Configure environment variables
cat > .env.test <<EOF
QUILT_MULTIUSER_MODE=true
QUILT_TEST_CATALOG_URL=https://test-catalog.quiltdata.com
QUILT_TEST_JWT_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
QUILT_TEST_GRAPHQL_ENDPOINT=https://api.test-catalog.quiltdata.com/graphql
EOF

# 4. Load environment variables
export $(cat .env.test | xargs)

# 5. Verify authentication
uv run python -c "
from quilt_mcp.ops.factory import QuiltOpsFactory
ops = QuiltOpsFactory.create()
status = ops.get_auth_status()
print(f'Authenticated: {status.is_authenticated}')
print(f'Catalog: {status.catalog_name}')
"
```

### 3.3 Automated Authentication Setup

**Location:** `tests/e2e/fixtures/setup_authentication.py`

**Script Structure:**
```python
#!/usr/bin/env python3
"""
setup_authentication.py - Automated authentication setup

Validates authentication configuration for both modes.
"""

import os
import sys
from pathlib import Path
from quilt_mcp.ops.factory import QuiltOpsFactory
from quilt_mcp.ops.exceptions import AuthenticationError


def check_local_mode():
    """Check local mode authentication"""
    print("Checking local mode authentication...")

    os.environ["QUILT_MULTIUSER_MODE"] = "false"

    try:
        ops = QuiltOpsFactory.create()
        status = ops.get_auth_status()

        if status.is_authenticated:
            print(f"  ✓ Authenticated to {status.registry_url}")
            return True
        else:
            print(f"  ✗ Not authenticated")
            return False
    except AuthenticationError as e:
        print(f"  ✗ Authentication error: {e}")
        print(f"  Remediation: {e.context.get('remediation', 'Unknown')}")
        return False


def check_multiuser_mode():
    """Check multiuser mode authentication"""
    print("Checking multiuser mode authentication...")

    os.environ["QUILT_MULTIUSER_MODE"] = "true"

    # Check environment variables
    required_vars = [
        "QUILT_TEST_CATALOG_URL",
        "QUILT_TEST_JWT_TOKEN",
        "QUILT_TEST_GRAPHQL_ENDPOINT"
    ]

    for var in required_vars:
        if not os.getenv(var):
            print(f"  ✗ Missing environment variable: {var}")
            return False

    try:
        ops = QuiltOpsFactory.create()
        status = ops.get_auth_status()

        if status.is_authenticated:
            print(f"  ✓ Authenticated to {status.logged_in_url}")
            print(f"  ✓ Catalog: {status.catalog_name}")
            return True
        else:
            print(f"  ✗ Not authenticated")
            return False
    except AuthenticationError as e:
        print(f"  ✗ Authentication error: {e}")
        print(f"  Remediation: {e.context.get('remediation', 'Unknown')}")
        return False


def main():
    print("=== QuiltOps Authentication Setup ===\n")

    local_ok = check_local_mode()
    print()
    multiuser_ok = check_multiuser_mode()
    print()

    if local_ok and multiuser_ok:
        print("✓ Both modes configured correctly")
        return 0
    elif local_ok:
        print("⚠ Only local mode configured")
        return 1
    elif multiuser_ok:
        print("⚠ Only multiuser mode configured")
        return 1
    else:
        print("✗ No authentication configured")
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

**Usage:**
```bash
# Check authentication configuration
uv run python tests/e2e/fixtures/setup_authentication.py
```

---

## 4. CI/CD Integration

### 4.1 GitHub Actions Workflow

**Location:** `.github/workflows/e2e-quilt-ops.yml`

**Workflow:**
```yaml
name: E2E Tests - QuiltOps API

on:
  workflow_dispatch:  # Manual trigger
  schedule:
    - cron: '0 2 * * *'  # Nightly at 2 AM UTC

env:
  AWS_REGION: us-east-1
  QUILT_TEST_BUCKET_DATA: quilt-mcp-test-data
  QUILT_TEST_BUCKET_SCRATCH: quilt-mcp-test-scratch
  QUILT_TEST_BUCKET_PACKAGES: quilt-mcp-test-packages

jobs:
  test-local-mode:
    name: E2E Tests (Local Mode)
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_TEST_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Setup Python & uv
        uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync

      - name: Setup quilt3 session
        run: |
          uv run quilt3 login s3://${{ env.QUILT_TEST_BUCKET_PACKAGES }}

      - name: Check authentication
        run: |
          uv run python tests/e2e/fixtures/setup_authentication.py

      - name: Run e2e tests (local mode)
        env:
          QUILT_MULTIUSER_MODE: false
          QUILT_TEST_REGISTRY_URL: s3://${{ env.QUILT_TEST_BUCKET_PACKAGES }}
        run: |
          uv run pytest tests/e2e/quilt_ops/ \
            -v \
            -m "not requires_admin" \
            --junit-xml=test-results-local.xml \
            --html=test-report-local.html

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results-local
          path: |
            test-results-local.xml
            test-report-local.html

      - name: Cleanup test resources
        if: always()
        run: |
          uv run python tests/e2e/fixtures/cleanup_test_data.py

  test-multiuser-mode:
    name: E2E Tests (Multiuser Mode)
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_TEST_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Setup Python & uv
        uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync

      - name: Check authentication
        env:
          QUILT_TEST_CATALOG_URL: ${{ secrets.QUILT_TEST_CATALOG_URL }}
          QUILT_TEST_JWT_TOKEN: ${{ secrets.QUILT_TEST_JWT_TOKEN }}
          QUILT_TEST_GRAPHQL_ENDPOINT: ${{ secrets.QUILT_TEST_GRAPHQL_ENDPOINT }}
        run: |
          uv run python tests/e2e/fixtures/setup_authentication.py

      - name: Run e2e tests (multiuser mode)
        env:
          QUILT_MULTIUSER_MODE: true
          QUILT_TEST_CATALOG_URL: ${{ secrets.QUILT_TEST_CATALOG_URL }}
          QUILT_TEST_JWT_TOKEN: ${{ secrets.QUILT_TEST_JWT_TOKEN }}
          QUILT_TEST_GRAPHQL_ENDPOINT: ${{ secrets.QUILT_TEST_GRAPHQL_ENDPOINT }}
        run: |
          uv run pytest tests/e2e/quilt_ops/ \
            -v \
            --junit-xml=test-results-multiuser.xml \
            --html=test-report-multiuser.html

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results-multiuser
          path: |
            test-results-multiuser.xml
            test-report-multiuser.html

      - name: Cleanup test resources
        if: always()
        run: |
          uv run python tests/e2e/fixtures/cleanup_test_data.py

  notify:
    name: Notify on Failure
    needs: [test-local-mode, test-multiuser-mode]
    if: failure()
    runs-on: ubuntu-latest

    steps:
      - name: Send Slack notification
        uses: slackapi/slack-github-action@v1
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
          payload: |
            {
              "text": "QuiltOps E2E Tests Failed",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": ":x: *QuiltOps E2E Tests Failed*\n<${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|View Run>"
                  }
                }
              ]
            }
```

### 4.2 Required GitHub Secrets

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `AWS_TEST_ROLE_ARN` | IAM role for test execution | `arn:aws:iam::123456:role/quilt-mcp-test-role` |
| `QUILT_TEST_CATALOG_URL` | Test catalog URL | `https://test-catalog.quiltdata.com` |
| `QUILT_TEST_JWT_TOKEN` | JWT token for multiuser mode | `eyJhbGc...` |
| `QUILT_TEST_GRAPHQL_ENDPOINT` | GraphQL endpoint | `https://api.test-catalog.quiltdata.com/graphql` |
| `SLACK_WEBHOOK_URL` | Slack webhook for notifications | `https://hooks.slack.com/...` |

---

## 5. Cleanup and Maintenance

### 5.1 Automated Cleanup Script

**Location:** `tests/e2e/fixtures/cleanup_test_data.py`

**Script Structure:**
```python
#!/usr/bin/env python3
"""
cleanup_test_data.py - Clean up ephemeral test data

Removes temporary data from scratch bucket while preserving reference data.
"""

import boto3
import os


def cleanup_scratch_bucket():
    """Remove all objects from scratch bucket"""
    bucket_name = os.getenv("QUILT_TEST_BUCKET_SCRATCH", "quilt-mcp-test-scratch")

    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)

    print(f"Cleaning up {bucket_name}...")

    # Delete all objects
    objects_to_delete = [{'Key': obj.key} for obj in bucket.objects.all()]

    if objects_to_delete:
        bucket.delete_objects(Delete={'Objects': objects_to_delete})
        print(f"  ✓ Deleted {len(objects_to_delete)} objects")
    else:
        print(f"  ✓ No objects to delete")


def main():
    cleanup_scratch_bucket()


if __name__ == "__main__":
    main()
```

### 5.2 Monthly Maintenance Tasks

**Tasks:**
1. Review and update test data (regenerate if schema changed)
2. Rotate JWT tokens (expire monthly)
3. Review AWS costs (compare to baseline)
4. Update baseline packages (if new versions needed)
5. Archive old test results (keep last 90 days)

**Checklist:**
```markdown
## Monthly Maintenance Checklist

- [ ] Review test data schema (any changes needed?)
- [ ] Regenerate test data if schema changed
- [ ] Rotate JWT tokens for multiuser mode
- [ ] Review AWS costs (compare to $150/month baseline)
- [ ] Check for orphaned S3 objects in scratch bucket
- [ ] Update baseline packages if needed
- [ ] Archive test results older than 90 days
- [ ] Review and update documentation
- [ ] Check for flaky tests (>1% flake rate)
- [ ] Update dependencies (uv, pytest, quilt3)
```

---

## 6. Troubleshooting

### 6.1 Common Issues

#### Issue: Authentication Failures

**Symptoms:**
- Tests fail with `AuthenticationError`
- `get_auth_status()` returns `is_authenticated=False`

**Solutions:**
1. **Local Mode:**
   ```bash
   # Verify quilt3 session
   quilt3 whoami

   # Re-login if needed
   quilt3 login s3://quilt-mcp-test-packages
   ```

2. **Multiuser Mode:**
   ```bash
   # Check JWT token expiration
   echo $QUILT_TEST_JWT_TOKEN | jwt decode -

   # Refresh token from catalog UI
   open https://test-catalog.quiltdata.com
   ```

#### Issue: Missing Test Data

**Symptoms:**
- Tests fail with `NotFoundError` for test files
- `FileNotFoundError` when accessing S3 objects

**Solutions:**
```bash
# Verify test data exists
aws s3 ls s3://quilt-mcp-test-data/ --recursive

# Regenerate and upload test data
uv run python tests/e2e/fixtures/generate_test_data.py
aws s3 sync tests/e2e/fixtures/data/ s3://quilt-mcp-test-data/ --delete
```

#### Issue: Permission Denied

**Symptoms:**
- `PermissionError` or `AccessDenied` from AWS
- Tests fail to read/write S3 objects

**Solutions:**
```bash
# Check IAM role permissions
aws sts get-caller-identity

# Verify bucket policies
aws s3api get-bucket-policy --bucket quilt-mcp-test-data

# Test S3 access
aws s3 ls s3://quilt-mcp-test-data/
aws s3 cp test.txt s3://quilt-mcp-test-scratch/
```

### 6.2 Diagnostic Commands

```bash
# Check authentication status
uv run python -c "
from quilt_mcp.ops.factory import QuiltOpsFactory
ops = QuiltOpsFactory.create()
print(ops.get_auth_status())
"

# Verify test buckets accessible
aws s3 ls s3://quilt-mcp-test-data/
aws s3 ls s3://quilt-mcp-test-scratch/
aws s3 ls s3://quilt-mcp-test-packages/

# Check baseline packages
uv run python -c "
from quilt_mcp.ops.factory import QuiltOpsFactory
ops = QuiltOpsFactory.create()
packages = ops.list_all_packages(registry='s3://quilt-mcp-test-packages')
print(f'Found {len(packages)} packages')
for pkg in packages:
    print(f'  - {pkg}')
"

# Validate test data integrity
uv run python tests/e2e/fixtures/validate_checksums.py

# Run single test for debugging
uv run pytest tests/e2e/quilt_ops/test_01_authentication.py::Test_Authentication::test_local_mode_authentication -v -s
```

---

## 7. Cost Estimation

### 7.1 Monthly Cost Breakdown

| Resource | Usage | Cost/Month |
|----------|-------|-----------|
| S3 Storage (test-data) | 600 MB | $0.01 |
| S3 Storage (scratch) | 500 MB average | $0.01 |
| S3 Storage (packages) | 1 GB | $0.02 |
| S3 Requests (GET) | 10,000/day | $0.40 |
| S3 Requests (PUT) | 1,000/day | $0.50 |
| Data Transfer Out | 10 GB/month | $0.90 |
| Athena Queries | 100 queries @ 10MB | $0.05 |
| Glue Data Catalog | Storage | $1.00 |
| CloudWatch Logs | 1 GB | $0.50 |
| **Total** | | **~$3.39/month** |

**Nightly Test Run Cost:** ~$0.50/run
**Monthly Cost (30 runs):** ~$15/month
**Buffer for development:** ~$5/month

**Total Estimated Cost:** **$25/month**

### 7.2 Cost Optimization Strategies

1. **Lifecycle Policies:** Auto-delete scratch data after 24h
2. **Test Data Reuse:** Use immutable reference data (no re-upload)
3. **Selective Test Execution:** Skip slow tests during development
4. **Request Optimization:** Batch S3 operations where possible
5. **CloudWatch Log Retention:** Keep logs for 7 days only

---

## Conclusion

This infrastructure setup provides a complete, automated testing environment for QuiltOps e2e tests. The design emphasizes reproducibility, cost-effectiveness, and ease of maintenance.

**Key Features:**
- Dedicated S3 buckets with lifecycle policies
- Deterministic test data generation
- Dual-mode authentication support
- CI/CD integration with GitHub Actions
- Automated cleanup and cost monitoring

**Next Steps:**
1. Review and approve infrastructure design
2. Provision AWS resources (CloudFormation/Terraform)
3. Generate and upload test data
4. Create baseline packages
5. Configure CI/CD secrets
6. Run initial test suite validation
