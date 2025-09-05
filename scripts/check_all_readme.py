import quilt3

# All jump-consortium packages from the list
packages = [
    "jump-consortium/all-profiles-v1c",
    "jump-consortium/cell-painting-samples-overview",
    "jump-consortium/compound-complete-pipeline-v1",
    "jump-consortium/compound-profiles-v1-0-1",
    "jump-consortium/compound-profiles-v1",
    "jump-consortium/crispr-profiles-v1a",
    "jump-consortium/orf-profiles-v1a",
    "jump-consortium/pilot-sample-BR00116991",
    "jump-consortium/pilot-sample-BR00116992",
    "jump-consortium/pilot-sample-BR00116993-v2",
    "jump-consortium/pilot-sample-BR00116994-v2",
    "jump-consortium/pilot-sample-BR00116995-v2",
    "jump-consortium/pilot-sample-BR00116996-v2",
    "jump-consortium/pilot-sample-BR00116997-v2",
    "jump-consortium/sample-1053601756-v2",
    "jump-consortium/sample-1053601763-v2",
    "jump-consortium/sample-1053601770-v2",
    "jump-consortium/sample-1053601787-v2",
    "jump-consortium/sample-1053601794-v2",
    "jump-consortium/sample-1053601800-v2",
    "jump-consortium/sample-1053601817-v2",
    "jump-consortium/sample-1053601824-v2",
    "jump-consortium/sample-1053601831-v2",
    "jump-consortium/sample-1053601848-v2",
    "jump-consortium/sample-1053601855-v2",
    "jump-consortium/sample-1053601862-v2",
    "jump-consortium/sample-1053601879-v2",
    "jump-consortium/sample-1053601909-v2",
    "jump-consortium/sample-1053601923-v2",
    "jump-consortium/sample-1053601947-v2",
    "jump-consortium/sample-BR5867a3-v2",
    "jump-consortium/sample-BR5867b3-v2",
    "jump-consortium/sample-BR5867c3-v2",
    "jump-consortium/sample-BR5867d3-v2",
    "jump-consortium/sample-UL000109-complete",
    "jump-consortium/sample-UL000109-v2",
    "jump-consortium/sample-UL000109",
    "jump-consortium/sample-UL001641-v2",
    "jump-consortium/sample-UL001641",
    "jump-consortium/sample-UL001643-v2",
    "jump-consortium/sample-UL001643",
    "jump-consortium/sample-UL001645-v2",
    "jump-consortium/sample-UL001645",
    "jump-consortium/sample-UL001651-v2",
    "jump-consortium/sample-UL001651",
    "jump-consortium/sample-UL001653-v2",
    "jump-consortium/sample-UL001653",
    "jump-consortium/sample-UL001655-v2",
    "jump-consortium/sample-UL001655",
    "jump-consortium/sample-UL001659-v2",
    "jump-consortium/sample-UL001659",
    "jump-consortium/sample-UL001661-v2",
    "jump-consortium/sample-UL001661",
]

print(f"Checking {len(packages)} jump-consortium packages for README content in metadata...")
print("=" * 80)

results = {}
packages_with_readme = []
packages_without_readme = []

for i, package_name in enumerate(packages, 1):
    try:
        print(f"[{i:2d}/{len(packages)}] Checking {package_name}...", end=" ")
        pkg = quilt3.Package.browse(package_name, registry='s3://quilt-sandbox-bucket')

        has_readme_content = 'readme_content' in pkg.meta
        has_readme_file = 'README.md' in pkg.keys()

        if has_readme_content:
            readme_length = len(pkg.meta.get('readme_content', ''))
            packages_with_readme.append((package_name, readme_length))
            print(f"❌ HAS README IN METADATA ({readme_length} chars)")
        elif has_readme_file:
            print("✅ HAS README.md FILE")
        else:
            print("ℹ️  NO README")

        results[package_name] = {'has_readme_content': has_readme_content, 'has_readme_file': has_readme_file}

    except Exception as e:
        print(f"❌ ERROR: {str(e)[:50]}...")
        results[package_name] = {'error': str(e)}

print("\n" + "=" * 80)
print("SUMMARY:")
print(f"Total packages checked: {len(packages)}")

if packages_with_readme:
    print(f"\n❌ Packages with README content in metadata ({len(packages_with_readme)}):")
    for pkg_name, length in packages_with_readme:
        print(f"  - {pkg_name} ({length} chars)")
else:
    print("\n✅ All packages are clean - no README content in metadata!")

print("\n📊 Breakdown:")
readme_in_metadata = sum(1 for r in results.values() if isinstance(r, dict) and r.get('has_readme_content'))
readme_files = sum(1 for r in results.values() if isinstance(r, dict) and r.get('has_readme_file'))
errors = sum(1 for r in results.values() if isinstance(r, dict) and 'error' in r)

print(f"  - README in metadata: {readme_in_metadata}")
print(f"  - README.md files: {readme_files}")
print(f"  - Errors: {errors}")
print(f"  - Clean packages: {len(packages) - readme_in_metadata - errors}")
