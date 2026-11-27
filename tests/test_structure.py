"""Mechanical enforcement of docs/golden-principles.md.

Each test names the principle it guards. When a review or the periodic
clean-up sweep finds the same kind of problem twice, add a check here.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PACKAGE = SRC / "resume_platform"


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _modules() -> dict[str, Path]:
    """Dotted module name -> file, for every module in the package."""
    modules = {}
    for path in PACKAGE.rglob("*.py"):
        parts = path.relative_to(SRC).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules[".".join(parts)] = path
    return modules


def _imports(module: str, path: Path) -> set[str]:
    """Absolute names of everything ``module`` imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = package.split(".")
                anchor = anchor[: len(anchor) - (node.level - 1)]
                base = ".".join([*anchor, base] if base else anchor)
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return found


# --- Principle 1: dependencies point inward ---------------------------------

# layer -> layers it must not import
FORBIDDEN_IMPORTS = {
    "resume_platform.infrastructure": [
        "resume_platform.resume",
        "resume_platform.interfaces",
        "resume_platform.publishing",
        "resume_platform.vector_search",
        "resume_platform.resume_renderer",
    ],
    "resume_platform.resume": [
        "resume_platform.interfaces",
        "resume_platform.publishing",
        "resume_platform.vector_search",
        "resume_platform.resume_renderer",
    ],
    "resume_platform.resume_input_parser": ["resume_platform.interfaces"],
    "resume_platform.resume_renderer": [
        "resume_platform.interfaces",
        "resume_platform.publishing",
    ],
    "resume_platform.publishing": ["resume_platform.interfaces"],
    "resume_platform.vector_search": ["resume_platform.interfaces"],
    "resume_platform.paths": ["resume_platform."],
}


def test_dependencies_point_inward() -> None:
    violations = []
    for module, path in sorted(_modules().items()):
        for layer, banned in FORBIDDEN_IMPORTS.items():
            if module != layer and not module.startswith(layer + "."):
                continue
            for name in sorted(_imports(module, path)):
                if any(name.startswith(b) for b in banned):
                    violations.append(f"{_rel(path)} imports {name}")
    assert not violations, "\n".join(violations)


# --- Principle 2: resume persistence only through the repository -------------

RESUME_FS_ALLOWED = {
    "src/resume_platform/resume/repository.py": "owns the <version>.yaml layout",
    "src/resume_platform/infrastructure/filesystem.py": "defines it",
    "src/resume_platform/infrastructure/bootstrap.py": "initialises storage",
    "src/resume_platform/interfaces/mcp/server.py": "data:// raw file resource",
    "src/resume_platform/interfaces/mcp/tools.py": "diagnose_filesystems",
}


def test_resume_storage_is_only_touched_by_the_repository() -> None:
    offenders = [
        _rel(path)
        for path in PACKAGE.rglob("*.py")
        if "get_resume_fs" in path.read_text(encoding="utf-8")
        and _rel(path) not in RESUME_FS_ALLOWED
    ]
    assert not offenders, f"use resume.repository instead: {offenders}"


# --- Principle 3: failures raise --------------------------------------------


def _is_error_dict(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Dict) and any(
        isinstance(key, ast.Constant) and key.value == "error" for key in node.keys
    )


def _error_returns(path: Path) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Return):
            continue
        value = node.value
        dumped = (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr == "dumps"
            and value.args
            and _is_error_dict(value.args[0])
        )
        if _is_error_dict(value) or dumped:
            found.append(f"{_rel(path)}:{node.lineno} returns an error payload")
        if isinstance(
            value, (ast.Constant, ast.JoinedStr)
        ) and "[Error]" in ast.unparse(value):
            found.append(f"{_rel(path)}:{node.lineno} returns an '[Error]' string")
    return found


def test_failures_raise_instead_of_returning_errors() -> None:
    found = [hit for path in PACKAGE.rglob("*.py") for hit in _error_returns(path)]
    assert not found, "\n".join(found)


# --- Principle 4: MCP tools stay thin ----------------------------------------

MAX_TOOL_STATEMENTS = 4


def test_mcp_tools_are_thin() -> None:
    from resume_platform.interfaces.mcp.tools import TOOLS

    tools_path = PACKAGE / "interfaces" / "mcp" / "tools.py"
    tree = ast.parse(tools_path.read_text(encoding="utf-8"))
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    fat = []
    for spec in TOOLS:
        body = functions[spec.fn.__name__].body
        statements = [
            s
            for s in body
            if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
        ]
        if len(statements) > MAX_TOOL_STATEMENTS:
            fat.append(f"{spec.fn.__name__} ({len(statements)} statements)")
    # diagnose_filesystems is a report builder by nature.
    fat = [f for f in fat if not f.startswith("diagnose_filesystems")]
    assert not fat, f"move logic into the domain layer: {fat}"


# --- Principle 5: importing has no side effects ------------------------------


def test_importing_every_module_has_no_side_effects(tmp_path: Path) -> None:
    modules = sorted(_modules())
    logs_dir = tmp_path / "logs"
    script = "\n".join(
        [
            "import importlib, os, sys",
            f"os.environ['LOGS_DIR'] = {str(logs_dir)!r}",
            f"for name in {modules!r}: importlib.import_module(name)",
            "from resume_platform.infrastructure import filesystem",
            "from resume_platform.infrastructure.settings import settings",
            "print(settings.is_resolved, filesystem.is_initialized())",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=True,
    )
    assert result.stdout.split() == ["False", "False"], result.stderr
    assert not logs_dir.exists(), "an import created the logs directory"


# --- Principle 6: repo paths come from paths.py ------------------------------


def test_no_parent_path_arithmetic() -> None:
    allowed = {"src/resume_platform/paths.py"}
    offenders = [
        f"{_rel(path)}:{lineno}"
        for folder in (SRC, ROOT / "scripts")
        for path in folder.rglob("*.py")
        if _rel(path) not in allowed
        for lineno, line in enumerate(path.read_text("utf-8").splitlines(), 1)
        if re.search(r"\.parents?\[\d+\]", line) and not line.lstrip().startswith("#")
    ]
    assert not offenders, f"use resume_platform.paths instead: {offenders}"


# --- Principle 9: docs describe the present ----------------------------------

HISTORICAL_DOCS = {
    "docs/adr/0001-composition-root-and-runtime-lifecycle.md",
    "docs/mcp_tools_refactor_plan.md",
    "docs/resume_version_management.md",
}
# Names in docs that refer to things outside this repo.
EXTERNAL_REFS = {"claude_desktop_config.json", "main.tex", "resume.tex", "src/main.tex"}
FILE_REF = re.compile(
    r"`([A-Za-z0-9_.\-/]*[A-Za-z0-9_\-]\.(?:py|md|sh|toml|ya?ml|json|j2|tex|cls|env))`"
)
LINK_REF = re.compile(r"\]\(([^)#:\s]+)\)")


def _tracked(pattern: str) -> list[Path]:
    out = subprocess.check_output(["git", "ls-files", pattern], cwd=ROOT, text=True)
    return [ROOT / line for line in out.split()]


def test_docs_reference_existing_files() -> None:
    tracked_names = {path.name for path in _tracked("*")}
    missing = []
    for doc in [*_tracked("*.md"), ROOT / ".cursorrules"]:
        if _rel(doc) in HISTORICAL_DOCS:
            continue
        text = doc.read_text(encoding="utf-8")
        refs = set(FILE_REF.findall(text)) | set(LINK_REF.findall(text))
        for ref in sorted(refs - EXTERNAL_REFS):
            if "/" not in ref.rstrip("/"):
                ok = ref in tracked_names or (doc.parent / ref).exists()
            else:
                bases = (ROOT, doc.parent, SRC, PACKAGE)
                ok = any((base / ref).exists() for base in bases)
            if not ok:
                missing.append(f"{_rel(doc)} -> {ref}")
    assert not missing, "\n".join(missing)


# --- Principle 10: delete what nobody uses -----------------------------------


def _orphan_candidates(tracked: list[str]) -> list[str]:
    """Standalone files that only matter if something mentions them by name.

    Package modules, templates loaded by pattern and fixture data directories
    are covered elsewhere (imports, ruff, tests) and are not listed here.
    """
    out = []
    for path in tracked:
        parts = Path(path).parts
        top_level_script = len(parts) == 1 and path.endswith(".sh")
        if (
            parts[0] in ("scripts", "schemas")
            or (parts[0] == "templates" and len(parts) == 2)
            or (parts[:2] == ("tests", "fixtures") and len(parts) == 3)
            or top_level_script
        ):
            out.append(path)
    return out


def test_no_unreferenced_files() -> None:
    tracked = [_rel(p) for p in _tracked("*") if p.is_file()]
    texts = {}
    for path in tracked:
        if path in HISTORICAL_DOCS or path == "uv.lock":
            continue  # history and lockfiles don't count as a reason to keep
        try:
            texts[path] = (ROOT / path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    orphans = [
        candidate
        for candidate in _orphan_candidates(tracked)
        if not any(
            Path(candidate).name in text
            for path, text in texts.items()
            if path != candidate
        )
    ]
    assert not orphans, (
        f"Nothing references these files; delete them or document them: {orphans}"
    )


@pytest.mark.parametrize("doc", sorted(HISTORICAL_DOCS))
def test_historical_docs_are_marked(doc: str) -> None:
    head = (ROOT / doc).read_text(encoding="utf-8")[:1500].lower()
    assert "status" in head, f"{doc} must state its status near the top"
