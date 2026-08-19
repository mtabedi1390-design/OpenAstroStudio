# Plugin Specification

**Status:** Draft v0.1 · Companion to [ARCHITECTURE.md](ARCHITECTURE.md), [CAPABILITY_MODEL.md](CAPABILITY_MODEL.md), [SECURITY.md](SECURITY.md)

A plugin is the unit of ecosystem extension: a versioned, signed, manifest-described
package that contributes Capabilities, Providers, Tools, schemas, adapters, environments
recipes, documentation, and tests — **without modifying the kernel**.

---

## 1. Plugin ≠ Python file

A plugin is a directory (distributed as an archive / installable dist) with a formal
manifest. Python is one possible implementation language of a plugin's adapters, not
the definition of a plugin. A plugin that wraps a CLI tool or an instrument may contain
no importable Python at all beyond generated adapter stubs.

```
smk-plugin-astropy-coordinates/
├── plugin.yaml                  # THE manifest (required)
├── capabilities/                # capability documents this plugin defines (optional)
│   └── coordinate-transformation.capability.yaml
├── schemas/                     # dataset/parameter schemas (optional)
│   └── point-list.schema.json
├── src/smk_plugin_astropy/      # adapter code (optional; language per runtime)
├── recipes/                     # environment recipes (optional)
│   └── default.env.yaml
├── tests/                       # plugin's own tests incl. conformance bindings
├── docs/
└── CHANGELOG.md
```

## 2. Manifest (`plugin.yaml`)

Canonical JSON schema `schema:smk/plugin-manifest@1`; YAML authoring accepted.
All fields below are normative; (†) marks required.

```yaml
schema_version: 1                                  # †
identity:                                          # †
  id: org.astropy.coordinates                      # † reverse-DNS, registry-unique
  version: 1.2.0                                   # † semver
  display_name: Astropy Coordinates
  publisher: astropy-community
  license: BSD-3-Clause                            # † SPDX id
  homepage: https://…
  signature: …                                     # detached sig; see SECURITY.md §3

compatibility:
  kernel_contract: ">=1,<2"                        # † plugin-contract version range
  platforms: [linux, macos, windows]

tools:                                             # software this plugin integrates
  - name: astropy
    kind: python-package                           # python-package | executable |
    ref: "astropy>=6,<8"                           #   container-image | service | instrument
    provenance: https://pypi.org/project/astropy/  # where the tool comes from

capabilities:                                      # defined by this plugin (optional)
  - ./capabilities/coordinate-transformation.capability.yaml

providers:                                         # see CAPABILITY_MODEL.md §1.2
  - name: skycoord-transform
    capability: cap:coords/coordinate-transformation@1
    tool: astropy
    invocation: { type: python-call, entrypoint: "smk_plugin_astropy.coords:transform", marshalling: json }
    requirements:
      runtimes: [ { type: python, version: ">=3.11", packages: ["astropy>=6"] } ]
      resources: { cpu: 1, memory_mb: 512 }
      permissions: []
    quality: { maturity: stable }
    health_check: { type: python-call, entrypoint: "smk_plugin_astropy.coords:health" }

runtimes:                                          # environments the plugin can run in
  - type: python
    recipe: ./recipes/default.env.yaml             # how to build one (env provider input)

permissions: []                                    # † union of all provider permissions;
                                                   # e.g. [ {fs: {read: ["$DATASET"]}} ,
                                                   #        {net: {hosts: ["archive.stsci.edu"]}} ]
                                                   # empty list = pure computation

schemas:
  - ./schemas/point-list.schema.json

documentation:
  readme: ./docs/README.md
  examples: [ ./docs/examples/m31.workflow.json ]

tests:
  conformance: ./tests/conformance.yaml            # binds providers → capability cases
  self_test: { type: process, argv: ["python", "-m", "pytest", "tests/"] }

health_checks:                                     # plugin-level (beyond per-provider)
  - { type: python-call, entrypoint: "smk_plugin_astropy:health" }
```

Validation rules (enforced at `VERIFIED` stage, KERNEL.md §3.2):
- Manifest schema-valid; all referenced files exist inside the plugin directory
  (no `..` escapes — path traversal is a verification failure).
- Every provider's `permissions` ⊆ plugin `permissions`.
- `kernel_contract` intersects the running kernel's contract version.
- Signature/hash requirements per trust level (SECURITY.md §3).

## 3. The plugin contract (code-level)

Adapter code interacts with the platform **only** through the SDK surface
(`smk.plugins.sdk`), which is versioned independently of kernel internals:

```python
# smk/plugins/sdk/contract.py
CONTRACT_VERSION = 1

class PluginRuntime(Protocol):
    """What a python-call provider entrypoint receives besides its inputs."""
    def workdir(self) -> Path: ...                  # sandboxed scratch dir
    def open_input(self, name: str) -> BinaryIO: ...    # marshalled per invocation
    def emit_output(self, name: str, payload: Any) -> None: ...
    def emit_artifact(self, path: Path, media_type: str, role: str) -> ArtifactRef: ...
    def log(self, level: str, message: str) -> None: ...
    def progress(self, fraction: float, note: str = "") -> None: ...
    def check_cancelled(self) -> bool: ...

# Entry point signature for python-call providers:
def provider_entrypoint(inputs: dict[str, Any], runtime: PluginRuntime) -> dict[str, Any]: ...
# Health check signature:
def health(runtime: PluginRuntime) -> HealthReport: ...
```

Notes:
- Entry points run **in the execution environment**, not in the kernel process
  (EXECUTION_MODEL.md §6). The SDK ships a thin runner that marshals inputs/outputs
  (JSON by default; `arrow`/`file` marshalling for large data, DATA_MODEL.md §6).
- Non-Python providers (`process`, `container-run`, `service-call`, `instrument-op`)
  have no code contract — their contract *is* the invocation spec + schemas; the SDK
  provides argv/stdin templating and output-file mapping (EXECUTION_MODEL.md §3).
- Plugins never import `smk.kernel.*`. CI for first-party plugins enforces this.

## 4. Tools

A `Tool` names the external software and pins how it is obtained. This is what allows
the platform to answer "what is actually installed, from where, at which version?" and
to record it in provenance. Tools are metadata + install recipes; the environment
providers do the installing (EXECUTION_MODEL.md §7).

## 5. Lifecycle & distribution

- **Package format**: `<id>-<version>.smkplugin` = zip of the plugin dir +
  `MANIFEST.sha256` (file hash list) + optional detached signature. Pure-Python adapter
  code may additionally be a normal wheel dependency of the plugin.
- **Sources**: registry (by id), local directory (`--from-dir`, dev mode), archive file,
  git URL. Source affects default trust level (SECURITY.md §3).
- **Install** = fetch → verify → materialize under `~/.smk/plugins/<id>/<version>/` →
  register in StateStore → health check → ACTIVE. Failed installs roll back fully
  (InstallError leaves no partial state).
- **Multiple versions** may be installed; exactly one is ACTIVE per plugin id.
- **Dev mode**: `scientific plugin dev ./path` symlinks a working directory as a
  `local-dev` trust plugin with live reload on manifest change — the primary plugin
  authoring loop.

## 6. Contract stability policy

- `CONTRACT_VERSION` (SDK) and `schema:smk/plugin-manifest@N` evolve by semver:
  additive optional fields in minors; breaking changes bump the major, and the kernel
  supports the previous manifest major for ≥2 minor kernel releases with conversion.
- A plugin declares `kernel_contract`; the PluginHost refuses (QUARANTINED, clear error)
  rather than best-effort-loads an incompatible plugin.

## 7. What plugins can contribute (extension points)

| Extension point | Mechanism |
|---|---|
| Capabilities | capability documents |
| Providers | manifest `providers` |
| Dataset schemas | `schemas/` |
| Environment recipes | `recipes/` |
| Workflow node UI hints | provider metadata (`ui:` block, optional; GUI-interpreted) |
| CLI verbs | **not allowed** (kernel/CLI surface stays closed; avoids namespace chaos) |
| Executors | **separate contract** — executors are not plugins (EXECUTION_MODEL.md §4); they extend infrastructure, need deeper trust, and are versioned separately |
| Agents | separate contract (AGENT_MODEL.md); same reasoning |

## 8. The SDK developer kit

`sdk/` ships:
- `smk plugin new` scaffolding templates (python-call, process, container, instrument).
- `PluginContractTests` — the conformance suite every plugin must pass
  (`scientific plugin test .`): manifest validity, permission-subset rule, entrypoint
  loadability in a fresh env, health check, conformance-case execution, marshalling
  round-trips, no-kernel-import rule.
- The same suite is executed by registries on submission (REGISTRY.md §6) and by the
  IntegrationAgent when it generates plugins (AGENT_MODEL.md §6) — one bar for humans,
  registries, and AI.

## 9. Reference plugins (kept in-tree, ROADMAP Phases 3/8)

1. `python-runtime` — machinery that turns Python callables into providers: the MVP's
   reflection engine + manual-override pattern live here.
2. `cli-runtime` — machinery for wrapping executables: argv templates, exit-code maps,
   stdout/stderr/file output mapping.
3. `astropy` — the migrated MVP integration (SkyCoord construction, frame transform,
   separation), including conformance cases reproducing the MVP's known-good outputs.
   This is the permanent "smallest real scientific integration" and the migration
   fitness function (ARCHITECTURE.md §12).

## 10. Testable contracts (Phase 3 gate)

- Manifest schema: valid/invalid corpus incl. path-traversal, permission-superset,
  contract-mismatch cases.
- Lifecycle: install/rollback atomicity; quarantine on each failure class; version
  switch; dev-mode reload.
- SDK runner: marshalling round-trips (json/file), cancellation propagation,
  artifact emission → DataCatalog registration.
- `PluginContractTests` passes for all three reference plugins on all supported
  platforms in CI.
