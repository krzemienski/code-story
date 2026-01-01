#!/usr/bin/env python3
"""Export OpenAPI schema to JSON and YAML files.

Usage:
    python scripts/export_openapi.py

Output:
    docs/openapi.json
    docs/openapi.yaml
"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def export_openapi() -> None:
    """Export OpenAPI schema to JSON and YAML files."""
    try:
        import yaml
    except ImportError:
        print("PyYAML not installed. Run: pip install pyyaml")
        sys.exit(1)

    # Import app after path setup
    from codestory.api.main import app
    from codestory.api.config.openapi import custom_openapi

    # Generate schema
    schema = custom_openapi(app)

    # Create output directory
    docs_dir = Path(__file__).parent.parent / "docs" / "api"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Export as JSON
    json_path = docs_dir / "openapi.json"
    with open(json_path, "w") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    print(f"✓ Exported: {json_path}")

    # Export as YAML
    yaml_path = docs_dir / "openapi.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(schema, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"✓ Exported: {yaml_path}")

    # Print summary
    paths_count = len(schema.get("paths", {}))
    schemas_count = len(schema.get("components", {}).get("schemas", {}))
    print(f"\nOpenAPI Schema Summary:")
    print(f"  Version: {schema.get('openapi', 'unknown')}")
    print(f"  Title: {schema.get('info', {}).get('title', 'unknown')}")
    print(f"  API Version: {schema.get('info', {}).get('version', 'unknown')}")
    print(f"  Endpoints: {paths_count}")
    print(f"  Schemas: {schemas_count}")


if __name__ == "__main__":
    export_openapi()
