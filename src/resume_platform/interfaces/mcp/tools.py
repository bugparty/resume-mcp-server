"""The MCP tool surface.

Conventions (keep new tools consistent with these):

* A resume is addressed by ``version_name`` (file stem, no ``.yaml``); a
  section by ``section_id``. Text tools take an optional ``section_id`` —
  omitted means the whole-resume text view.
* Failures raise; FastMCP turns the exception message into a tool error.
  Tools never return ``"[Error] ..."`` strings or ``{"error": ...}`` payloads.
* Reads return data (``dict``) or Markdown (``str``); writes return a short
  confirmation, or the updated state when it is small (layout tools).
* Tools are thin: logic lives in ``resume_platform.resume`` /
  ``resume_platform.publishing`` / ``resume_platform.vector_search``.

Each tool is registered in :data:`TOOLS` with its MCP annotations; tools
flagged ``writes_resume`` also mark the vector index stale after success.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Literal

from pydantic import Field

from resume_platform import publishing, vector_search
from resume_platform.infrastructure.filesystem import (
    get_jd_fs,
    get_output_fs,
    get_resume_fs,
    is_initialized,
)
from resume_platform.infrastructure.settings import get_settings
from resume_platform.resume import editing, layout, versions, views
from resume_platform.resume.repository import list_versions

from .prompts import RESUME_AGENT_PROMPT, resume_yaml_format_doc

VersionName = Annotated[
    str,
    Field(description="Resume version name without .yaml, e.g. 'resume'."),
]
SectionId = Annotated[
    str,
    Field(
        description="Section id, e.g. 'header', 'summary', 'skills', 'experience'. "
        "See list_resume_sections."
    ),
]
OptionalSectionId = Annotated[
    str | None,
    Field(
        description="Section id to target one section; omit to target the "
        "whole-resume text view."
    ),
]


# --- Versions -----------------------------------------------------------------


def list_resume_versions() -> dict[str, Any]:
    """List all stored resume versions."""
    names = list_versions()
    return {"versions": names, "total": len(names)}


def create_resume_version(version_name: VersionName) -> str:
    """Create a new resume version from the blank standard template.

    To start from existing content, use copy_resume_version instead.
    """
    return versions.create_version(version_name)


def copy_resume_version(
    source_version: Annotated[str, Field(description="Existing version to copy.")],
    target_version: Annotated[
        str, Field(description="New version name; must not exist yet.")
    ],
) -> str:
    """Copy an existing resume version to a new version name."""
    return versions.copy_version(source_version, target_version)


def delete_resume_version(version_name: VersionName) -> str:
    """Permanently delete a resume version. The base 'resume' version cannot
    be deleted."""
    return versions.delete_version(version_name)


# --- Reading ------------------------------------------------------------------


def load_complete_resume(version_name: VersionName) -> str:
    """Render a resume version as read-only Markdown, with its layout
    (section order / hidden sections) applied."""
    return views.render_resume_markdown(version_name)


def list_resume_sections(version_name: VersionName) -> dict[str, Any]:
    """List the sections of a version with their id, type, title, whether they
    are rendered, and a Markdown format hint for editing."""
    sections = views.list_sections(version_name)
    return {"version_name": version_name, "sections": sections, "total": len(sections)}


def read_resume_text(
    version_name: VersionName, section_id: OptionalSectionId = None
) -> str:
    """Read the editable Markdown text of a whole resume or of one section.

    Use this before replace/insert/delete_resume_text to copy exact snippets.
    """
    return views.read_resume_text(version_name, section_id)


# --- Editing ------------------------------------------------------------------


def replace_resume_text(
    version_name: VersionName,
    old_text: Annotated[
        str, Field(description="Exact snippet to replace; must match exactly once.")
    ],
    new_text: Annotated[str, Field(description="Replacement text.")],
    section_id: OptionalSectionId = None,
) -> str:
    """Replace one exact text snippet in the resume text view."""
    return editing.replace_text(version_name, old_text, new_text, section_id)


def insert_resume_text(
    version_name: VersionName,
    new_text: Annotated[str, Field(description="Text to insert.")],
    position: Annotated[
        Literal["start", "end", "before", "after"],
        Field(description="Where to insert, relative to the text or the anchor."),
    ],
    anchor_text: Annotated[
        str | None,
        Field(description="Required for before/after; must match exactly once."),
    ] = None,
    section_id: OptionalSectionId = None,
) -> str:
    """Insert text at the start/end of the text view, or before/after an anchor."""
    return editing.insert_text(
        version_name, new_text, position, anchor_text, section_id
    )


def delete_resume_text(
    version_name: VersionName,
    old_text: Annotated[
        str, Field(description="Exact snippet to delete; must match exactly once.")
    ],
    section_id: OptionalSectionId = None,
) -> str:
    """Delete one exact text snippet from the resume text view."""
    return editing.delete_text(version_name, old_text, section_id)


def update_resume_section(
    version_name: VersionName,
    section_id: SectionId,
    new_content: Annotated[
        str,
        Field(
            description="Complete new Markdown for the section, following the "
            "format_hint from list_resume_sections."
        ),
    ],
) -> str:
    """Rewrite one whole section from Markdown. Prefer the text tools for
    small edits. Only one section can be updated per call."""
    return editing.update_section(version_name, section_id, new_content)


# --- Layout -------------------------------------------------------------------


def get_resume_layout(version_name: VersionName) -> dict[str, Any]:
    """Get the section order and hidden sections used when rendering."""
    return {"version_name": version_name, **layout.get_layout(version_name)}


def set_section_visibility(
    version_name: VersionName,
    section_id: SectionId,
    enabled: Annotated[bool, Field(description="True to show, False to hide.")] = True,
) -> dict[str, Any]:
    """Show or hide a section when rendering. Returns the updated layout."""
    result = layout.set_section_visibility(version_name, section_id, enabled)
    return {"version_name": version_name, **result}


def set_section_order(
    version_name: VersionName,
    order: Annotated[
        list[str],
        Field(
            description="Section ids in the desired order. Unknown ids are "
            "skipped; unlisted sections follow in their current order."
        ),
    ],
) -> dict[str, Any]:
    """Set the rendering order of sections. Returns the updated layout."""
    return {
        "version_name": version_name,
        **layout.set_section_order(version_name, order),
    }


# --- Semantic search ----------------------------------------------------------


def build_vector_index(
    force_rebuild: Annotated[
        bool, Field(description="Re-embed every chunk instead of reusing cache.")
    ] = False,
) -> dict[str, Any]:
    """Build or refresh the semantic index of experience/project entries."""
    return vector_search.build_index(force_rebuild=force_rebuild)


def search_resume_entries(
    query: Annotated[str, Field(description="Natural-language search query.")],
    entry_type: Literal["experience", "projects", "all"] = "all",
    chunk_level: Annotated[
        Literal["entry", "bullet"],
        Field(description="Match whole entries or individual bullets."),
    ] = "entry",
    top_k: Annotated[int, Field(ge=1, le=50)] = 5,
) -> dict[str, Any]:
    """Semantic search over experience/project entries across all versions."""
    return vector_search.search_entries(
        query=query, entry_type=entry_type, chunk_level=chunk_level, top_k=top_k
    )


def get_vector_index_status() -> dict[str, Any]:
    """Report whether the semantic index exists and is up to date."""
    return vector_search.get_index_status()


# --- Rendering ----------------------------------------------------------------


def render_resume_pdf(version_name: VersionName) -> dict[str, str]:
    """Compile a resume version to PDF, upload it, and return a download link.

    Returns `public_url`, `filename`, `pdf_path` and `latex_assets_dir`.
    """
    return publishing.publish_pdf(version_name)


def render_resume_to_overleaf(version_name: VersionName) -> dict[str, str]:
    """Export a resume version as a LaTeX project and return an Overleaf link.

    Returns `overleaf_url`, `public_url`, `filename`, `zip_path` and
    `latex_assets_dir`.
    """
    return publishing.publish_overleaf(version_name)


# --- Help & diagnostics -------------------------------------------------------


def get_resume_yaml_format() -> str:
    """Documentation of the resume YAML format: JSON schema, section types and
    a complete example."""
    return resume_yaml_format_doc()


def call_me_at_the_first_time_when_you_are_chatgpt() -> str:
    """REQUIRED first call for ChatGPT clients: returns the usage guide for
    this server. Call it once before using any other tool."""
    return RESUME_AGENT_PROMPT


def _summarize_fs(fs_obj: Any, sample_size: int = 20) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "backend": f"{type(fs_obj).__module__}.{type(fs_obj).__name__}"
    }
    try:
        entries = sorted(fs_obj.listdir("."))
        summary.update(count=len(entries), sample=entries[:sample_size])
    except Exception as exc:  # diagnostics must report, not raise
        summary["error"] = f"{type(exc).__name__}: {exc}"
    return summary


def diagnose_filesystems() -> dict[str, Any]:
    """Report storage configuration and contents, for troubleshooting."""
    settings = get_settings()
    report: dict[str, Any] = {
        "initialized": is_initialized(),
        "settings": {
            "resume_fs_url": settings.resume_fs_url,
            "jd_fs_url": settings.jd_fs_url,
        },
        "env": {
            key: os.getenv(key)
            for key in ("RESUME_FS_URL", "RESUME_FS_UR", "JD_FS_URL")
        },
    }
    for name, getter in (
        ("resume_fs", get_resume_fs),
        ("jd_fs", get_jd_fs),
        ("output_fs", get_output_fs),
    ):
        try:
            report[name] = _summarize_fs(getter())
        except Exception as exc:
            report[name] = {"error": f"{type(exc).__name__}: {exc}"}
    report["versions"] = list_versions()
    return report


# --- Registry -----------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    fn: Callable[..., Any]
    read_only: bool
    writes_resume: bool = False
    destructive: bool = False
    open_world: bool = False

    @property
    def annotations(self) -> dict[str, bool]:
        return {
            "readOnlyHint": self.read_only,
            "idempotentHint": self.read_only,
            "destructiveHint": self.destructive,
            "openWorldHint": self.open_world,
        }


def _read(fn: Callable[..., Any]) -> ToolSpec:
    return ToolSpec(fn, read_only=True)


def _write(fn: Callable[..., Any], *, destructive: bool = False) -> ToolSpec:
    return ToolSpec(fn, read_only=False, writes_resume=True, destructive=destructive)


TOOLS: tuple[ToolSpec, ...] = (
    _read(call_me_at_the_first_time_when_you_are_chatgpt),
    # versions
    _read(list_resume_versions),
    _write(create_resume_version),
    _write(copy_resume_version),
    _write(delete_resume_version, destructive=True),
    # reading
    _read(load_complete_resume),
    _read(list_resume_sections),
    _read(read_resume_text),
    # editing
    _write(replace_resume_text),
    _write(insert_resume_text),
    _write(delete_resume_text),
    _write(update_resume_section),
    # layout
    _read(get_resume_layout),
    _write(set_section_visibility),
    _write(set_section_order),
    # search
    ToolSpec(build_vector_index, read_only=False),
    _read(search_resume_entries),
    _read(get_vector_index_status),
    # rendering
    ToolSpec(render_resume_pdf, read_only=False, open_world=True),
    ToolSpec(render_resume_to_overleaf, read_only=False, open_world=True),
    # help & diagnostics
    _read(get_resume_yaml_format),
    _read(diagnose_filesystems),
)
