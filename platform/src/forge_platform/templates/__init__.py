import json
import os
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent


def list_templates() -> list[dict]:
    """List all available templates."""
    templates = []
    for f in sorted(TEMPLATE_DIR.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
            templates.append({
                "id": f.stem,
                "name": data["name"],
                "description": data["description"],
                "icon": data.get("icon", "table"),
                "table_count": len(data.get("tables", [])),
                "view_count": len(data.get("views", [])),
                "form_count": len(data.get("forms", [])),
                "has_dashboard": "dashboard" in data,
            })
    return templates


def get_template(template_id: str) -> dict | None:
    """Load a template by ID."""
    path = TEMPLATE_DIR / f"{template_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)
