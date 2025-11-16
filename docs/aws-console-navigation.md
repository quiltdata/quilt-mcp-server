# How to View Elasticsearch Indices in AWS Console

## OpenSearch Domain: tf-dev-bench

**Console URL:** https://us-east-2.console.aws.amazon.com/aos/home?region=us-east-2#opensearch/domains/tf-dev-bench

## Steps to View Indices

### Option 1: OpenSearch Dashboards (Recommended)

1. On the domain overview page, look for **"OpenSearch Dashboards URL"** in the top section
2. Click the URL (something like: `https://vpc-tf-dev-bench-xxx.us-east-2.es.amazonaws.com/_dashboards/`)
3. Once in Dashboards:
   - Click the menu (☰) in top-left
   - Navigate to: **Management** → **Dev Tools**
   - In the console, run:
     ```
     GET _cat/indices?v
     ```
   - This will list ALL indices with their names, document counts, and sizes

### Option 2: Indices Tab

1. On the domain overview page
2. Look for tabs at the top: **"General information"**, **"Indices"**, **"Alarms"**, etc.
3. Click the **"Indices"** tab
4. This should show a list of all indices in the cluster

### Option 3: Dev Tools via Console Actions

1. On the domain overview page
2. Click **"Actions"** dropdown button (top-right)
3. Look for option like **"Launch OpenSearch Dashboards"** or **"Run queries"**
4. Follow OpenSearch Dashboards steps above

## What to Look For

Once you can see the indices list, look for indices containing:
- `quilt-ernest-staging` (your default bucket)
- Pattern: `{bucket_name}` (files)
- Pattern: `{bucket_name}_packages` (package entries? or manifests?)
- Any indices with `-reindex-` in the name (reindexed versions)

## To View Index Mapping (Structure)

In OpenSearch Dashboards Dev Tools console:
```
GET quilt-ernest-staging/_mapping
GET quilt-ernest-staging_packages/_mapping
```

## To View Sample Documents

In OpenSearch Dashboards Dev Tools console:
```
GET quilt-ernest-staging/_search
{
  "size": 1
}

GET quilt-ernest-staging_packages/_search
{
  "size": 1
}
```

This will show the actual document structure with all fields.
