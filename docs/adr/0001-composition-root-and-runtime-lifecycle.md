# ADR-0001: Composition root and explicit runtime lifecycle

**Status:** Proposed
**Date:** 2026-07-16
**Deciders:** @bugparty
**Scope:** Fixes finding **A** ("global mutable singletons as the state backbone") from the 2026-07-16 architecture review.

## Context

Process state — application settings and the three PyFilesystem2 backends
(`_resume_fs`, `_jd_fs`, `_output_fs`) — is held in module-level mutable
globals and established as a **side effect of importing modules**. There is no
single place that assembles runtime state; every entry point and every test
re-does it, each with its own guard pattern:

- `interfaces/mcp/server.py:429` initializes filesystems **at import time**,
  before `mcp = FastMCP(...)` is even created. (Ironically, `main()` then logs
  `"Filesystems initialized"` at `server.py:1720` without initializing
  anything — the log line is false.)
- `vector_search.py:213` re-implements a near-identical `is_initialized()`
  guard and initializes lazily on first use.
- `resume_renderer.py:813` initializes only inside its CLI `main()`, unguarded.
- **Six test modules** (`test_resume_operations`, `test_resume_rendering`,
  `test_basic_functions`, `test_quick_toolkit`, `test_quick_version_workflow`,
  plus direct calls in `test_filesystem`) each run
  `load_settings(...)` + `init_filesystems(...)` **at import scope**, unguarded.

Because the filesystems are process-global and `get_resume_fs()` raises
`RuntimeError` until `init_filesystems()` has run, "who imported first" decides
who wins, and any test that resets the globals breaks every later test that
relied on some other module's import-time initialization.

This is not a hypothetical. Three recently-merged fixes are all symptoms of
this single root cause:

- **#15** — a filesystem-global reset in one test broke 61 unrelated tests
  (`RuntimeError: Resume filesystem not initialized`).
- **#16** — `resume_input_parser` resolved settings, created `logs_dir`, and
  opened a log file at import time; deferred to first use.
- **#14** was unrelated (parser correctness), but landed in the same
  "patch the instance, not the class" cadence the maintainer flagged as
  *"修修补补"*.

As long as state is established by import side effects, this class of bug
regenerates. We are fixing instances, not the cause.

### Forces at play

- The read API — `get_settings()`, `get_resume_fs()`, `get_jd_fs()`,
  `get_output_fs()` — is called from dozens of sites and must **not** change.
- The suite currently passes (102 tests); the fix must not regress it.
- Two real entry points exist (MCP stdio via `mcp.run()`, and an HTTP/ASGI app
  factory), plus CLI scripts and the test harness. Each needs state assembled
  exactly once, deterministically.
- The current `RESUME_ALLOW_MEM_FS_FALLBACK` env switch lets a failed
  filesystem init silently degrade to `mem://`. This hides misconfiguration.

## Prior art: Django

Django solves exactly this problem, and splits it into two orthogonal,
co-existing mechanisms. We model our design on both.

**1. A lazy settings proxy.** `django.conf.settings` is not a settings object —
it is a `LazySettings` proxy. Importing `django.conf` has *zero* side effects;
the proxy resolves on **first attribute access**, at which point `_setup()`
reads the `DJANGO_SETTINGS_MODULE` env var and builds the real `Settings`.
`settings.configure(**opts)` can inject settings programmatically before first
access; resolving after configure (or reconfiguring after resolve) is an error.
The invariant "import does not resolve settings" is *structural* — no module
has to remember to defer, because the proxy defers for everyone.

**2. An explicit composition root, `django.setup()`.** State is assembled by one
idempotent function, not by import order. It calls `apps.populate()`, whose
registry (`django.apps.apps`, a module-level singleton) is:
- **lock-guarded and idempotent** — `with self._lock:` then `if self.ready: return`;
- **reentrancy-checked** — a re-entrant `populate()` raises
  `RuntimeError("populate() isn't reentrant")` rather than deadlocking or looping;
- **phased** — `apps_ready → models_ready → ready`, three explicit ordered passes,
  so ordering never depends on who imported first.

Every entry point calls `setup()` explicitly: `get_wsgi_application()` and
`get_asgi_application()` on their first line, and `manage.py`/`django-admin` via
`ManagementUtility.execute()`.

The mapping to our design:

| Django | Ours |
|--------|------|
| `django.setup()` | `bootstrap()` |
| `apps._lock` + `apps.ready` | `bootstrap`'s lock + `_ready` flag |
| `apps_ready → models_ready → ready` | `settings → filesystems → logging` phases |
| WSGI/ASGI/manage.py each call `setup()` | `server.main()` / HTTP app factory / conftest fixture each call `bootstrap()` |
| `LazySettings` proxy | `LazySettings` proxy over `AppSettings` (new) |

## Decision

Introduce a **lazy settings proxy** (modeled on `django.conf.settings`) and a
**single composition root** (modeled on `django.setup()`), and remove all
import-time initialization.

1. **Lazy settings proxy.** Add a `LazySettings` proxy as the module global
   `settings` in `infrastructure/settings.py`. It resolves on first attribute
   access and caches the result; importing any module no longer resolves
   settings or touches env. `settings.configure(**overrides)` injects overrides
   before first access (used by tests and `bootstrap`); resolving after
   configure, or reconfiguring after resolve, raises. `get_settings()` stays as
   the accessor and returns the resolved `AppSettings`, so the dozens of
   existing call sites are unchanged. This makes "import does not resolve
   settings" a *structural* property rather than something each module must
   remember (it is what the #16 parser snapshot got wrong).

2. **Composition root `bootstrap()` — our `django.setup()`.** New module
   `infrastructure/bootstrap.py` with one `bootstrap()` that runs explicit
   ordered phases `settings → filesystems → logging`. Modeled on
   `apps.populate()`: **lock-guarded and idempotent** (second call no-ops),
   **reentrancy-checked** (a re-entrant call raises rather than deadlocking),
   phases explicit so ordering never depends on import order. Low-level
   `init_filesystems()` / `reset_filesystems()` and the settings builder stay
   as-is; `bootstrap()` only orchestrates, so the diff is additive.

3. **Every entry point calls `bootstrap()` explicitly** — `server.main()`, the
   HTTP app factory `_build_dual_http_app()`, and an `autouse`/`scope="session"`
   `conftest.py` fixture — the way WSGI/ASGI/manage.py each call
   `django.setup()`. The import-time call at `server.py:429` and the per-module
   import-time bootstrap in all six test files are deleted; the suite becomes
   order-independent by construction. Logging setup (`_initialize_logging`)
   folds into `bootstrap`; `mcp_log_file` is assigned during bootstrap, not at
   import. The one test that mutates globals keeps the function-scoped
   `preserve_global_filesystems` fixture from #15.

4. **Fail loud: the `mem://` fallback is removed.** `bootstrap()` raises on
   filesystem-init failure. The `RESUME_ALLOW_MEM_FS_FALLBACK` env switch and
   the silent-degradation path in `_ensure_server_filesystems_initialized` are
   deleted. A misconfigured backend must surface immediately, not masquerade as
   a working server backed by throwaway in-memory storage.

### Reference design

`infrastructure/settings.py` — lazy proxy (mirrors `LazySettings`):

```python
class LazySettings:
    """Resolve settings on first access, not at import. Mirrors django.conf.settings."""

    def __init__(self) -> None:
        self._wrapped: AppSettings | None = None
        self._overrides: dict[str, Any] = {}

    def configure(self, **overrides: Any) -> None:
        if self._wrapped is not None:
            raise RuntimeError("settings already resolved; configure() must precede first access")
        self._overrides = overrides

    def _resolve(self) -> AppSettings:
        if self._wrapped is None:
            self._wrapped = load_settings(**self._overrides)  # reads env + overrides
        return self._wrapped

    def reset(self) -> None:  # for bootstrap(force=True) / tests
        self._wrapped = None
        self._overrides = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)


settings = LazySettings()            # import-time: zero side effects


def get_settings() -> AppSettings:   # unchanged accessor for existing call sites
    return settings._resolve()
```

`infrastructure/bootstrap.py` — composition root (mirrors `django.setup()` +
`apps.populate()`):

```python
"""The one place process state is assembled: settings → filesystems → logging."""
from __future__ import annotations
import threading
from typing import Any
from resume_platform.infrastructure import filesystem as fs
from resume_platform.infrastructure.settings import settings, get_settings, AppSettings

_lock = threading.Lock()
_ready = False
_running = False  # reentrancy guard, à la apps.populate()


def bootstrap(*, force: bool = False, **settings_overrides: Any) -> AppSettings:
    """Assemble runtime state once. Safe to call from any entry point.

    Idempotent (second call no-ops unless force=True); reentrant calls raise;
    raises on filesystem-init failure — there is no silent mem:// fallback.
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
                settings.reset()
                fs.reset_filesystems()
            # phase 1 — settings
            if settings_overrides:
                settings.configure(**settings_overrides)
            resolved = get_settings()          # resolves lazily, exactly once
            # phase 2 — filesystems
            if not fs.is_initialized():
                fs.init_filesystems(resolved.resume_fs_url, resolved.jd_fs_url)
            # phase 3 — logging
            configure_logging(resolved)         # folded-in _initialize_logging
            _ready = True
            return resolved
        finally:
            _running = False
```

`tests/conftest.py`:

```python
@pytest.fixture(scope="session", autouse=True)
def _bootstrap_runtime():
    from resume_platform.infrastructure.bootstrap import bootstrap
    fixtures = Path(__file__).parent / "fixtures" / "test_data"
    bootstrap(
        data_dir=os.getenv("TEST_RESUME_DATA_DIR") or fixtures / "resumes",
        jd_dir=os.getenv("TEST_RESUME_JD_DIR") or fixtures / "jd",
    )
```

## Options Considered

### Option A: Single composition root + explicit lifecycle (chosen)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low — additive; wraps existing `init_*` primitives |
| Blast radius | Read API unchanged; ~8 files touched, mostly deletions |
| Test isolation | Order-independent by construction |
| Familiarity | Standard composition-root pattern |

**Pros:** Kills the whole bug class at the source; one obvious place state is
built; entry points become honest; deletes duplicated bootstrap in 6 test files
and 2 prod guards. **Cons:** Touches production startup (staged into PR-2 to
isolate risk); requires deleting the mem fallback that someone may have relied
on for local debugging.

### Option B: Auto-initializing accessors (lazy `get_*_fs()`)

Make `get_resume_fs()` call `init_filesystems()` from default settings if the
global is `None`, so the `RuntimeError` becomes impossible.

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low |
| Blast radius | Accessor semantics change everywhere |
| Test isolation | Worse — hides ordering, picks up ambient settings |
| Familiarity | Common but an anti-pattern here |

**Pros:** Smallest diff; no test changes. **Cons:** Hides initialization order
instead of fixing it; a test pointing settings at fixtures could still race an
accessor that already lazily initialized from defaults. Trades a loud failure
for a silent wrong-data failure. **Rejected.**

### Option C: Dependency injection — thread an `AppContext` through call sites

Pass an explicit context object instead of using module globals at all.

| Dimension | Assessment |
|-----------|------------|
| Complexity | High — rewrites dozens of signatures |
| Blast radius | Every `get_*` call site and the whole tool layer |
| Test isolation | Best possible |
| Familiarity | Standard, but large migration |

**Pros:** The "correct" long-term shape; no globals. **Cons:** Far larger than
finding A warrants right now; would collide with the still-pending decisions on
the vestigial `tools.py`/model layers (findings B–D). **Deferred** — Option A
does not preclude migrating to this later.

## Trade-off Analysis

The real choice is A vs B: **fix the ordering** vs **hide the ordering**. B is
tempting because it needs no test changes, but it converts a loud, correct
failure (`RuntimeError` — "you forgot to initialize") into a quiet, incorrect
one (accessor silently initialized from ambient defaults, so a test reads the
wrong data dir). Option A makes initialization a single explicit event and lets
the accessors keep failing loudly when that event hasn't happened — which is
exactly the property that makes the suite deterministic.

C is where the codebase should eventually go, but sequencing it now would
entangle this fix with the unresolved layer-removal decisions (findings B–D)
and balloon the diff. A is a strict step toward C, not away from it.

Removing the `mem://` fallback is a deliberate strictness increase: a server
that "works" on in-memory storage after an S3 misconfiguration is worse than
one that refuses to start, because the failure surfaces later as silent data
loss.

## Consequences

**Easier**
- Test suite is order-independent; the #15/#16 bug class stops regenerating.
- One obvious place to understand or change startup.
- Entry-point logs stop lying about what has been initialized.
- Six test files and two production guard functions shed duplicated bootstrap.
- Import purity becomes *structural* (the proxy defers for everyone), not a
  discipline each module must remember — the exact failure mode behind #16.

**Harder / to revisit**
- Local debugging that leaned on `RESUME_ALLOW_MEM_FS_FALLBACK` must now use an
  explicit `mem://` config (e.g. a documented `RESUME_FS_URL=mem://`) instead
  of a silent degrade. This is intended.
- The HTTP app factory must call `bootstrap()` too, since ASGI servers may load
  it without going through `main()`. Both paths must be covered.
- `bootstrap()` keeps a small amount of module-level state (`_ready`,
  `_running`, `_lock`). It is process-global by nature but has a single writer,
  a lock, and an explicit `force` reset, unlike the scattered globals it
  replaces — the same shape as Django's `apps.ready`/`apps._lock`.
- The `LazySettings` proxy adds one layer of `__getattr__` indirection over
  settings access. This is mild "magic," justified because it makes the
  import-purity invariant impossible to violate; Django accepts the same
  trade-off. Debuggers/`repr` see a proxy until first resolve — worth a note in
  the settings module docstring.

## Action Items

**PR-1 — test-side stop-the-bleed (🟢 low risk, no production startup change)**
1. [ ] Add `infrastructure/bootstrap.py` with the lock/phase/reentrancy-guarded
       `bootstrap()` (+ `configure_logging`). Phase 1 uses `load_settings()`
       directly for now; PR-3 swaps it to the proxy's `configure()`.
2. [ ] Add the `autouse`/session `_bootstrap_runtime` fixture to `conftest.py`.
3. [ ] Delete the import-scope `load_settings()`+`init_filesystems()` blocks from
       the six test modules.
4. [ ] Verify: full suite green (expect 102 passed); then re-run under shuffled
       order and per-file isolation to prove order-independence.

**PR-2 — production boot cleanup (🟠 medium risk)**
5. [x] Move the `server.py:429` import-time init into `main()` and
       `_build_dual_http_app()`; make the `"Filesystems initialized"` log true.
6. [x] Defer `_initialize_logging`; assign `mcp_log_file` lazily.
       **Deviation:** not folded into `bootstrap()` as originally proposed.
       `mcp_server.log` / `mcp_error_events.jsonl` are MCP-interface concerns,
       and teaching `infrastructure/bootstrap.py` about them would invert the
       layering this ADR is trying to protect. Instead the server keeps a lazy,
       lock-guarded `_ensure_logging()` (same shape as the parser fix in #16),
       called from the entry points and defensively from the failure-event
       helpers. `bootstrap()` stays generic.
7. [x] Route `vector_search._ensure_filesystems_initialized` through `bootstrap()`;
       delete its duplicated guard.
8. [x] **Delete the `mem://` fallback**: remove `RESUME_ALLOW_MEM_FS_FALLBACK`
       handling and the silent-degrade branch; `bootstrap()` raises on failure.
       (No doc update needed — the env var was never documented. `.env.sample`
       already shows `mem://` as an explicit config, which is the sanctioned
       replacement.)
9. [x] Verify: smoke-boot both transports (stdio + HTTP) and confirm the server
       starts and the log file is actually created.

**PR-3 — lazy settings proxy (🟠 medium risk, structural)**
10. [x] Introduce `LazySettings` as the `settings` global in `settings.py`; keep
        `get_settings()`/`load_settings()` working so call sites are untouched.
11. [x] Switch `bootstrap()` phase 1 from `load_settings(**o)` to
        `settings.configure(**o)` + `get_settings()`.
12. [x] **Make `load_settings()` a pure builder.** This turned out to be the
        substantive half of PR-3, and it is what actually kills the settings
        pollution: the function no longer reassigns a process global, so a
        caller that merely wants to inspect env parsing cannot repoint the
        process. The `reset_runtime_after` band-aid PR-1 added to
        `test_load_settings_accepts_resume_fs_ur_alias` is removed — the bug it
        contained is gone at the root.
13. [x] Route the remaining duplicated `load_settings()` + `init_filesystems()`
        bootstraps (`resume_renderer` CLI, `scripts/summarize_resumes.py`)
        through `bootstrap()`.
14. [x] Verify: `tests/test_settings_proxy.py` asserts import resolves nothing,
        `load_settings()` does not install, and configure-after-resolve raises;
        old-vs-new pollution comparison run directly.

    *Sequencing note:* PR-3 is independent of PR-1's stop-the-bleed and can move
    earlier, but it is the change that makes import-purity structural, so it is
    cheapest to land after the entry points already funnel through `bootstrap()`.

## Implementation notes

Two latent bugs surfaced while implementing PR-1 that the old import-time
initialization had been masking. Both are pre-existing, neither was introduced
by this work:

- **Collection pointed the filesystems at real data.** Importing the MCP server
  (which test collection does) ran its import-time initializer against *default*
  settings, so the globals pointed at the real `data/resumes` — the suite was
  one `is_initialized()` guard away from reading production data. The old
  per-module `init_filesystems()` calls masked it by re-initializing at import,
  last-writer-wins. The session fixture uses `force=True` to guarantee the
  fixture tree regardless.
- **`load_settings()` leaks through the settings global.**
  `test_load_settings_accepts_resume_fs_ur_alias` reassigns `_SETTINGS` to an
  S3 URL; anything reading `get_settings()` afterwards inherits it and tries to
  reach S3 (`NoCredentialsError`). Contained with `reset_runtime_after` in PR-1;
  **fixed at the root in PR-3** by making `load_settings()` a pure builder, and
  the band-aid removed. Verified old-vs-new: on `main` the same call sequence
  leaves `get_settings()` pointed at the S3 URL; now it is unaffected.

Also collapsed in PR-2: the `try/except ImportError` block in `server.py` whose
two branches imported an identical symbol list, making the `except` provably
dead. It sat on the exact lines that had to change to import `bootstrap`, and
duplicating the new import into a dead branch was not defensible.

Observed but left alone (out of scope): `load_dotenv()` still runs at
`server.py` import. It only populates `os.environ`, but it is the last
import-time side effect in that module and belongs in a later cleanup.

## Notes

- Deliberately out of scope: findings **B** (dead langchain `StructuredTool`
  layer), **C** (unused `langgraph`/`langsmith` deps), **D** (abandoned
  `agent_resume` typed model), **E–G**. Those get their own ADRs; this one is
  confined to runtime-state lifecycle so it can land safely and first.
