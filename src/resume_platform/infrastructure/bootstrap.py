"""The composition root: the one place process runtime state is assembled.

Modeled on ``django.setup()`` / ``django.apps.apps.populate()``. Every entry
point — the MCP server's ``main()``, the HTTP app factory, and the test
harness — calls :func:`bootstrap` exactly once instead of relying on
import-time side effects. See
``docs/adr/0001-composition-root-and-runtime-lifecycle.md``.

This PR-1 increment covers the ``settings -> filesystems`` phases, which is
what removes the import-order dependence behind the test-pollution bug class.
Folding logging setup into this function, and swapping phase 1 onto the lazy
settings proxy, are tracked as later increments in the ADR.
"""

from __future__ import annotations

import threading
from typing import Any

from resume_platform.infrastructure import filesystem as fs
from resume_platform.infrastructure.settings import (
    AppSettings,
    get_settings,
    load_settings,
)

_lock = threading.Lock()
_ready = False
_running = False  # reentrancy guard, à la apps.populate()


def bootstrap(*, force: bool = False, **settings_overrides: Any) -> AppSettings:
    """Assemble runtime state once. Safe to call from any entry point.

    Idempotent: a second call is a no-op that returns the current settings,
    unless ``force=True`` tears state down and rebuilds it (tests that need a
    clean slate). ``settings_overrides`` are forwarded to ``load_settings`` so
    tests can point at fixture directories without touching the environment.

    Reentrant calls raise rather than deadlocking. Filesystem-init failure
    propagates — there is no silent ``mem://`` fallback.
    """
    global _ready, _running
    with _lock:
        if _ready and not force:
            return get_settings()
        if _running:
            raise RuntimeError("bootstrap() isn't reentrant")
        _running = True
        try:
            if force:
                fs.reset_filesystems()
            # phase 1 — settings
            settings = load_settings(**settings_overrides)
            # phase 2 — filesystems
            if not fs.is_initialized():
                fs.init_filesystems(settings.resume_fs_url, settings.jd_fs_url)
            _ready = True
            return settings
        finally:
            _running = False
