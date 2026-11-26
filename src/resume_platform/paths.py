"""Well-known locations inside the repository.

Centralised so modules don't compute ``Path(__file__).parents[N]`` themselves;
that pattern silently broke whenever a module moved (e.g. the MCP server
looked for ``schemas/`` under ``src/``).
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = PROJECT_ROOT / "templates"
LATEX_TEMPLATE_DIR = TEMPLATES_DIR / "latex"
RESUME_TEMPLATE_PATH = TEMPLATES_DIR / "resume_template.yaml"
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
RESUME_SCHEMA_PATH = SCHEMAS_DIR / "resume_schema.json"
DATA_DIR = PROJECT_ROOT / "data"

# Files copied next to the generated .tex for compilation / Overleaf export.
LATEX_ASSET_FILES = ("awesome-cv.cls", "profile.png")
LATEX_ASSET_DIRS = ("fonts",)
