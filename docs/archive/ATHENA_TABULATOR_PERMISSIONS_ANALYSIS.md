# Athena/Tabulator Permissions Analysis - Root Cause & Solution

## 🎯 **Executive Summary**

After examining the Quilt repositories, I've identified the **exact root cause** of our Athena/Tabulator failures and the **specific permissions needed** to fix them. The issue is **missing Glue permissions** in our IAM role, which are **required for Athena to access database metadata**.

## 🔍 **Root Cause Analysis**

### **The Error We're Seeing**
```
User: arn:aws:sts::850787717197:assumed-role/ReadWriteQuiltV2-sales-prod/simon@quiltdata.io 
is not authorized to perform: glue:GetDatabase on resource: arn:aws:glue:us-east-1:850787717197:database/default
```

### **Why This Happens**
1. **Athena Requires Glue**: AWS Athena uses AWS Glue Data Catalog as its metadata store
2. **Database Access**: Every Athena query must first access the Glue database to understand table schemas
3. **Missing Permissions**: Our `ReadWriteQuiltV2-sales-prod` role lacks Glue permissions
4. **Tabulator Dependency**: Tabulator creates tables in Glue and requires these same permissions

## 📋 **Required Permissions (From Quilt Enterprise)**

Based on the enterprise repository analysis, here are the **exact permissions** needed:

### **Glue Permissions**
```json
{
  "Effect": "Allow",
  "Action": [
    "glue:GetDatabase",
    "glue:GetDatabases", 
    "glue:GetTable",
    "glue:GetTables"
  ],
  "Resource": [
    "arn:aws:glue:us-east-1:850787717197:catalog",
    "arn:aws:glue:us-east-1:850787717197:database/*",
    "arn:aws:glue:us-east-1:850787717197:table/*/*"
  ],
  "Condition": {
    "ForAnyValue:StringEquals": {
      "aws:CalledVia": "athena.amazonaws.com"
    }
  }
}
```

### **Athena Permissions** 
```json
{
  "Effect": "Allow",
  "Action": [
    "athena:BatchGetNamedQuery",
    "athena:BatchGetQueryExecution", 
    "athena:GetNamedQuery",
    "athena:GetQueryExecution",
    "athena:GetQueryResults",
    "athena:GetWorkGroup",
    "athena:StartQueryExecution",
    "athena:StopQueryExecution",
    "athena:ListNamedQueries",
    "athena:ListQueryExecutions",
    "athena:ListWorkGroups",
    "athena:ListDataCatalogs",
    "athena:ListDatabases"
  ],
  "Resource": "*"
}
```

### **S3 Permissions for Athena Results**
```json
{
  "Effect": "Allow",
  "Action": [
    "s3:GetBucketLocation",
    "s3:GetObject", 
    "s3:PutObject",
    "s3:AbortMultipartUpload",
    "s3:ListMultipartUploadParts"
  ],
  "Resource": [
    "arn:aws:s3:::athena-results-bucket",
    "arn:aws:s3:::athena-results-bucket/*"
  ],
  "Condition": {
    "ForAnyValue:StringEquals": {
      "aws:CalledVia": "athena.amazonaws.com"
    }
  }
}
```

## 🏗 **How Quilt Enterprise Sets This Up**

### **1. Database Creation**
- **Environment Variable**: `QUILT_USER_ATHENA_DATABASE` (e.g., `"sales-prod-database"`)
- **CloudFormation Output**: `UserAthenaDatabaseName` 
- **Purpose**: Dedicated Glue database for each Quilt stack

### **2. Workgroup Management**
- **Pattern**: `QuiltUserAthena-{stack-name}-{role-id}-{random}`
- **Configuration**: Enforced result location, query limits
- **Discovery**: Our MCP correctly discovers these workgroups

### **3. Table/View Creation**
For each bucket, Quilt creates:
- `{bucket}_packages` - Package metadata table
- `{bucket}_manifests` - Object metadata table  
- `{bucket}_packages-view` - Queryable package view
- `{bucket}_objects-view` - Queryable object view

### **4. Tabulator Tables**
- **Dynamic Creation**: Admin-configured via YAML
- **Schema Mapping**: CSV/Parquet files → SQL tables
- **Cross-Package Queries**: Aggregates data across packages

## 🔧 **Immediate Fix Required**

### **Step 1: Update IAM Role**
Add these permissions to `ReadWriteQuiltV2-sales-prod` role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:GetTable", 
        "glue:GetTables"
      ],
      "Resource": "*",
      "Condition": {
        "ForAnyValue:StringEquals": {
          "aws:CalledVia": "athena.amazonaws.com"
        }
      }
    }
  ]
}
```

### **Step 2: Verify Database Access**
Check what databases are available:
```bash
aws glue get-databases --region us-east-1
```

### **Step 3: Test Athena Access**
```sql
SHOW DATABASES;
```

## 📊 **Current MCP Implementation Analysis**

### **✅ What's Working**
1. **Workgroup Discovery**: Correctly finds Quilt workgroups
2. **Credential Handling**: Properly uses quilt3 session credentials
3. **Connection String**: Correctly formatted for PyAthena
4. **Tabulator Integration**: Successfully lists tabulator tables

### **❌ What's Blocked**
1. **Database Access**: Can't access Glue databases due to permissions
2. **Query Execution**: All SQL queries fail at metadata stage
3. **Table Discovery**: Can't list tables in databases

### **🔍 MCP Code Quality**
The MCP implementation is **architecturally sound**:
- Proper credential management
- Dynamic workgroup discovery
- Correct PyAthena integration
- Good error handling

**The issue is purely IAM permissions, not code.**

## 🎯 **Expected Behavior After Fix**

### **Athena Queries Should Work**
```sql
-- List databases
SHOW DATABASES;

-- Query package metadata
SELECT * FROM "sales-prod-database"."quilt-sandbox-bucket_packages-view" LIMIT 10;

-- Query tabulator tables
SELECT * FROM "sales-prod-tabulator"."quilt-sandbox-bucket"."gene_expression_data" LIMIT 10;
```

### **Tabulator Functionality**
- ✅ List tabulator tables (already working)
- ✅ Execute SQL queries against tabulated data
- ✅ Cross-package analytics and aggregation
- ✅ Longitudinal analysis capabilities

## 🚨 **Why This Is Critical for Enterprise**

### **Business Impact**
1. **Analytics Blocked**: No SQL-based data analysis
2. **Reporting Disabled**: No business intelligence queries  
3. **Research Hindered**: No longitudinal studies
4. **Compliance Issues**: Can't generate audit reports

### **Technical Debt**
- **Incomplete Setup**: Athena infrastructure exists but unusable
- **User Confusion**: Tools appear available but fail
- **Support Burden**: Users can't understand why queries fail

## 🛠 **Implementation Steps**

### **Immediate (This Week)**
1. **Add Glue Permissions**: Update IAM role with required permissions
2. **Test Database Access**: Verify `glue:GetDatabase` works
3. **Validate Queries**: Test basic Athena queries
4. **Document Databases**: List available databases for users

### **Short Term (Next Sprint)**  
1. **Tabulator Configuration**: Set up additional tabulator tables
2. **User Training**: Document how to use Athena/Tabulator
3. **Query Examples**: Provide sample queries for common use cases
4. **Monitoring**: Set up CloudWatch for query performance

### **Long Term (Future)**
1. **Cost Controls**: Implement query cost limits
2. **Performance Optimization**: Tune workgroup configurations  
3. **Advanced Features**: Enable open query for external tools
4. **Integration**: Connect with BI tools like Tableau

## 🏆 **Success Metrics**

### **Technical Validation**
- [ ] `SHOW DATABASES` returns results
- [ ] Package queries execute successfully
- [ ] Tabulator queries return data
- [ ] Cross-package joins work

### **User Experience**
- [ ] Longitudinal analysis queries complete
- [ ] Business intelligence reports generate
- [ ] Research workflows unblocked
- [ ] No permission-related support tickets

## 📋 **Action Items**

### **For DevOps Team**
1. **Update IAM Policy**: Add Glue permissions to `ReadWriteQuiltV2-sales-prod`
2. **Test Access**: Verify database access after update
3. **Document Changes**: Update infrastructure documentation

### **For Data Team**  
1. **Test Queries**: Validate Athena functionality after fix
2. **Create Examples**: Document common query patterns
3. **Train Users**: Provide Athena/Tabulator training

### **For Product Team**
1. **Update Documentation**: Reflect working Athena capabilities
2. **Plan Features**: Roadmap for advanced analytics features
3. **Gather Feedback**: User requirements for additional functionality

## 🎯 **Bottom Line**

The Athena/Tabulator failure is a **simple IAM permissions issue** with a **straightforward fix**. The MCP implementation is correct, the infrastructure exists, we just need to **add Glue permissions to the IAM role**.

**Impact**: This single change will unlock **complete SQL analytics capabilities** across all Quilt packages and enable **enterprise-grade data workflows**.

**Timeline**: **15-minute fix** with **immediate business value**.

---
*Analysis based on quiltdata/quilt and quiltdata/enterprise repository examination*  
*Date: 2025-08-27*  
*Branch: feature/mcp-comprehensive-testing*
