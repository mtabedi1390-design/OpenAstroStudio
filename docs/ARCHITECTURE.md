# Architecture Specification

**Status:** Draft v0.1 (Phase 0 deliverable)
**Working name:** SMK — *Scientific Meta-Kernel* (final name TBD; the CLI working name is `scientific`)

This document is the top-level architecture specification for transforming the AstroStudio
MVP into a universal scientific computing and integration platform. It defines the design
principles, module boundaries, repository structure, and migration strategy. Companion
documents specify each subsystem in detail:

| Document | Scope |
|---|---|
| [KERNEL.md](KERNEL.md) | Kernel services, domain model, event bus, persistence, lifecycles |
| [CAPABILITY_MODEL.md](CAPABILITY_MODEL.md) | Capability/Provider abstractions and the resolution pipeline |
| [PLUGIN_SPEC.md](PLUGIN_SPEC.md) | Plugin manifest, contract, lifecycle, packaging |
| [EXECUTION_MODEL.md](EXECUTION_MODEL.md) | Execution providers, workload spec, execution state machine |
| [AGENT_MODEL.md](AGENT_MODEL.md) | AI agent contracts, planning, approval boundaries |
| [DATA_MODEL.md](DATA_MODEL.md) | Datasets, artifacts, schemas, units, resources |
| [PROVENANCE.md](PROVENANCE.md) | Provenance records and reproducibility |
| [SECURITY.md](SECURITY.md) | Permissions, trust levels, sandboxing, audit |
| [REGISTRY.md](REGISTRY.md) | Registry architecture and index format |
| [ROADMAP.md](ROADMAP.md) | Phased delivery plan with usable artifacts per phase |

---

## 1. Vision in one sentence

> Integrate the scientific world instead of rebuilding it: a small, stable,
> domain-agnostic kernel through which scientific software, environments, data,
> AI agents, and instruments interoperate.

The kernel never implements science. It implements the *contracts* that let scientific
tools be discovered, installed, connected, executed, observed, and reproduced.

## 2. The central abstraction

The answer to "what is the smallest universal abstraction that allows fundamentally
different scientific software, environments, data, AI agents, and instruments to
interoperate?" is a triple:

```
Capability  —  what can be done          (a versioned, schema-typed contract)
Provider    —  what implements it        (a plugin-declared binding of a Capability
                                          to a concrete tool + invocation recipe)
Execution   —  where/how it runs         (a provider-agnostic workload submitted to
                                          an ExecutionProvider, producing Artifacts
                                          + a Provenance record)
```

Everything else in the platform is infrastructure around this triple:

- **Plugins** package Providers (and Capabilities, schemas, adapters).
- **Registries** index Plugins/Capabilities/Providers for discovery.
- **Environments** are the runtimes Executions need (venv, conda, container, remote…).
- **Workflows** are graphs whose nodes are Capability invocations (not Python functions).
- **Datasets/Artifacts** are the typed inputs/outputs flowing between Executions.
- **Instruments** are Providers whose backing implementation is hardware.
- **Agents** are planners that emit *plans of kernel API calls*, gated by policy.
- **Provenance** is the kernel-level record of every Execution.

A Python function, a CASA task, a Docker container, a telescope, and an AI model all
project onto this same triple. That is what makes the kernel domain-agnostic.

## 3. Design principles (normative)

1. **Small kernel.** The kernel contains no domain knowledge (no astronomy, no FITS,
   no CASA). Domain knowledge lives in plugins, schemas, registries, and agents.
   A new science domain must require *zero kernel changes*.
2. **Contracts over code.** Subsystems interact only through versioned, documented
   interfaces (Python `Protocol`s + JSON-schema'd data). Any component with a contract
   is replaceable.
3. **Kernel is headless.** GUI, CLI, notebooks, and agents are *clients* of the same
   kernel API. Nothing is possible in the GUI that is impossible via the API.
4. **Capability-first discovery.** Users search for *what* ("spectral analysis"),
   not *which package*.
5. **Untrusted by default.** Plugins, AI-generated code, and third-party tools are
   never assumed trusted. All side effects flow through the policy engine (SECURITY.md).
6. **Provenance is not optional.** Every Execution produces a provenance record.
   It is a kernel invariant, not a plugin courtesy.
7. **No fake functionality.** A capability/provider/executor is only registered when
   its health check passes. Documentation must not claim unimplemented features
   ("supports Docker" requires a passing Docker conformance test in CI).
8. **Local-first and open.** The platform is fully usable offline, without paid AI
   APIs, against a local registry. Cloud anything is optional.
9. **Composition over expansion.** New functionality arrives as plugins, providers,
   executors, and agents — not as kernel growth.

## 4. System overview

```
┌──────────────────────────────  Clients  ──────────────────────────────┐
│   GUI (workspaces)      CLI (`scientific …`)      Notebook / SDK      │
│   Agents (Planner, Integration, …)  — agents are ALSO just clients    │
└──────────────────────────────┬────────────────────────────────────────┘
                               │  Kernel API (in-process Python API +
                               │  local JSON-RPC service façade)
┌──────────────────────────────▼────────────────────────────────────────┐
│                            KERNEL (small)                             │
│                                                                       │
│  CapabilityResolver   PluginHost     ExecutionFabric    EventBus      │
│  (find/compare/plan)  (load/verify)  (schedule/monitor) (pub/sub)     │
│                                                                       │
│  DataCatalog          ProvenanceStore   PolicyEngine    StateStore    │
│  (datasets/artifacts) (run records)     (permissions)   (persistence) │
└──────┬──────────────────┬──────────────────┬──────────────────────────┘
       │ plugin contract  │ executor contract│ registry contract
┌──────▼──────┐   ┌───────▼────────┐  ┌──────▼───────┐
│  Plugins    │   │ ExecutionProv. │  │  Registries  │
│ astropy,    │   │ local-process, │  │ local index, │
│ cli-tools,  │   │ python-venv,   │  │ community    │
│ instruments │   │ docker, ssh, … │  │ index(es)    │
└─────────────┘   └────────────────┘  └──────────────┘
```

The kernel is a Python library first (`import smk.kernel`), wrapped by an optional
long-running local service (JSON-RPC over a unix socket / named pipe) so that GUIs,
CLIs and agents in other processes share one kernel state. See KERNEL.md §6.

## 5. Module boundaries and repository structure

Target structure (a `src/` mono-package plus first-party plugins/executors kept in-tree
but installed as separate distributions so they can move out later):

```
repo/
├── src/smk/
│   ├── kernel/            # domain model, services, event bus, state store
│   │   ├── model/         # Capability, Provider, Plugin, Workflow, Dataset, … (pure data)
│   │   ├── services/      # resolver, plugin host, fabric façade, catalogs
│   │   ├── events.py      # event types + bus
│   │   └── errors.py      # kernel error taxonomy
│   ├── api/               # stable public API façade + JSON-RPC service
│   ├── capabilities/      # capability registry service + resolution pipeline
│   ├── execution/         # ExecutionProvider contract + fabric implementation
│   ├── plugins/           # plugin SDK: manifest parsing, validation, loader, test kit
│   ├── registry/          # registry client + local index implementation
│   ├── data/              # dataset/artifact catalog, content-addressed store
│   ├── provenance/        # provenance store + reproducibility checker
│   ├── security/          # policy engine, permission model, audit log
│   ├── agents/            # agent contracts + built-in agents (Phase 7)
│   └── cli/               # `scientific` CLI (thin client of api/)
├── executors/             # first-party execution providers (separate dists)
│   ├── local-process/
│   ├── python-venv/
│   └── docker/            # added only when conformance tests pass
├── plugins/               # first-party reference plugins (separate dists)
│   ├── python-runtime/    # generic "wrap a Python callable" provider machinery
│   ├── cli-runtime/       # generic "wrap a CLI tool" provider machinery
│   └── astropy/           # the migrated MVP astronomy integration (reference plugin)
├── gui/                   # Qt client (client of api/, never imports kernel internals)
├── sdk/                   # public plugin-developer kit: templates, contract test suite
├── tests/                 # unit / integration / contract / e2e suites
└── docs/                  # this specification set
```

**Dependency rule (enforced in CI with import-linter):**

```
kernel.model  ←  kernel.services  ←  api  ←  {cli, gui, agents}
kernel.*      ←  {capabilities, execution, plugins, registry, data, provenance, security}
```

- `kernel.model` imports nothing from the rest of the platform (pure dataclasses).
- Nothing in `src/smk` imports from `plugins/`, `executors/`, or `gui/`.
- `gui` and `cli` import only `smk.api`.
- Plugins import only `smk.plugins.sdk` (the stable SDK surface), never kernel internals.

## 6. Audit of the current MVP

### 6.1 What exists

~1,100 LOC PySide6 desktop prototype: reflection of Python callables into `NodeSpec`s
(`engine/reflection.py`), module scanning (`engine/library_scanner.py`), manual override
registry for dynamic signatures (`engine/overrides.py`), a DAG with topological sort
(`engine/graph.py`), transparent code generation (`engine/codegen.py`, injection-hardened
in PR #1), direct + generated-code execution (`engine/executor.py`), and a Qt node editor.

### 6.2 Architectural weaknesses (why it cannot be extended in place)

| # | Weakness | Consequence |
|---|---|---|
| W1 | `NodeSpec.callable_ref` holds a **live Python object** | Nodes cannot represent CLI tools, containers, remote services, or instruments; graphs are not serializable; execution is pinned to the GUI's own interpreter |
| W2 | Execution happens **in-process** in the GUI | No isolation, no remote/HPC path, one crash kills the app, no cancellation, no resource limits |
| W3 | No capability layer — nodes *are* implementations | Users must know package names; providers cannot be compared or substituted |
| W4 | No environment model | Only "whatever is importable in the GUI's venv" can run |
| W5 | No persistence — `Graph.to_dict()` exists but no load path, no project files | Work cannot be saved, versioned, or reproduced |
| W6 | No provenance, no events, no audit | Results are untraceable |
| W7 | GUI and engine are coupled (GUI constructs the default library, holds graph state) | Kernel is not headless |
| W8 | No plugin boundary — integrations are edits to the codebase (`libraries/`, `overrides.py`) | Third parties cannot extend without forking |
| W9 | No tests, no CI | Contracts cannot be enforced |

### 6.3 Reusable ideas and code

| MVP component | Fate |
|---|---|
| Reflection engine (`reflection.py`) | **Reused** inside the `python-runtime` plugin as the automatic provider generator for Python callables |
| Manual overrides pattern (`overrides.py`) | **Reused** as the plugin-level "curated provider" pattern; validates the 90% automatic / 10% manual strategy |
| Topological sort + cycle detection (`graph.py`) | **Reused** in the workflow scheduler (nodes become capability invocations) |
| Codegen transparency principle (`codegen.py`) | **Reused & generalized**: every workflow can be exported as a runnable script; the injection hardening carries over |
| Qt node editor / panels (`gui/`) | **Reused as a client**: rewired to render workflow graphs fetched from the kernel API instead of holding live objects |
| `execute_direct` in-process executor | **Demoted** to the `local-process` executor's "trusted, same-interpreter" fast path for interactive preview only |

## 7. Core domain model (summary)

Kernel-level nouns, all defined precisely in KERNEL.md §2 and DATA_MODEL.md:

`Capability`, `Provider`, `Tool`, `Plugin`, `Resource`, `Environment`, `Workflow`,
`WorkflowNode`, `Execution`, `Dataset`, `Artifact`, `Service`, `Instrument`, `Agent`,
`Project`, `Event`, `ProvenanceRecord`, `PermissionGrant`, `RegistryEntry`.

Identity convention (used everywhere, including registries and provenance):

```
cap:<namespace>/<name>@<major>          e.g. cap:coords/coordinate-transformation@1
provider:<plugin-id>/<provider-name>    e.g. provider:org.astropy.coordinates/skycoord-transform
plugin:<reverse-dns-id>@<semver>        e.g. plugin:org.astropy.coordinates@1.2.0
exec:<uuid>                             one Execution
artifact:sha256/<hex>                   content-addressed artifact
dataset:<uuid>@<version>
env:<provider-type>/<uuid>              e.g. env:python-venv/3f2a…
```

## 8. Interface strategy

- **In-process contracts** are Python `typing.Protocol`s (structural, statically checked
  with pyright in CI). Every contract lives in a `*_contract.py` module with a version
  constant (`CONTRACT_VERSION = 1`) and a conformance test suite in `sdk/`.
- **Data contracts** (manifests, workflow files, provenance records, registry indexes)
  are JSON-schema'd documents, versioned with `schema_version`. YAML is accepted as an
  authoring syntax; the canonical form is JSON.
- **Wire contract**: the local service exposes the same operations as `smk.api` via
  JSON-RPC 2.0. Method names mirror the CLI verb structure (`capability.search`,
  `plugin.install`, `execution.submit`, …).
- **Compatibility policy**: contracts follow semver. Kernel minor releases may add
  optional fields/methods; removals require a major version and a deprecation cycle of
  one minor release minimum.

## 9. Persistence and state (summary; details KERNEL.md §5)

- **StateStore**: SQLite (single-user local mode) behind a repository interface;
  swappable for Postgres in shared deployments. Holds installed plugins, environments,
  projects, workflow metadata, execution records, grants.
- **Content-addressed artifact store**: `~/.smk/store/sha256/<hex>` with a metadata row
  in StateStore. Artifacts are immutable.
- **Project files**: a project is a directory with `project.yaml` + `workflows/*.workflow.json`
  (schema'd, git-friendly, no live object references — fixes W1/W5).
- **Event log**: append-only table; the event bus persists all events for audit/replay.

## 10. Testing strategy (summary; per-phase gates in ROADMAP.md)

| Layer | Approach |
|---|---|
| Unit | Pure-model and service tests; kernel target ≥90% branch coverage |
| Contract | Reusable conformance suites shipped in `sdk/`: `PluginContractTests`, `ExecutorContractTests`, `RegistryContractTests`, `AgentContractTests`. First-party AND third-party implementations run the *same* suite |
| Integration | Real tiny integrations as fixtures: a pure-Python plugin, a CLI plugin wrapping a real binary (e.g. `sort`/`awk`-class tool), the astropy reference plugin |
| Execution | Each executor runs the conformance suite in CI (docker executor gated on a Docker-enabled CI job — otherwise it is not merged, per principle 7) |
| Security | Policy tests: permission denial paths, sandbox escape regression tests, injection corpus (extends the PR #1 regression tests) |
| Serialization | Round-trip + golden-file tests for every schema'd document; cross-version fixture matrix |
| E2E | CLI-driven scenario: install plugin → discover capability → build workflow → run → verify artifact + provenance → reproduce |

No subsystem merges without its contract tests. GUI features merge only after the
underlying API path has integration tests.

## 11. Failure-mode philosophy

Every contract defines its error taxonomy (kernel base: `SmkError` →
`ResolutionError | InstallError | ExecutionError | PolicyError | RegistryError |
PluginError | DataError`). Rules:

- Executions never vanish: any failure transitions the Execution state machine to a
  terminal `FAILED(reason)` state with logs and partial artifacts preserved (EXECUTION_MODEL.md §5).
- Plugin faults are contained: a plugin that fails to load/health-check is quarantined
  (state `QUARANTINED`), never crashes the kernel, and is reported via events.
- The kernel treats all subprocess/remote boundaries as unreliable: timeouts,
  retries-with-idempotency-keys, and heartbeats are part of the executor contract.

## 12. Migration strategy from the MVP

Incremental, always-shippable (details per phase in ROADMAP.md):

1. **Phase 1** introduces `src/smk/kernel` alongside the existing `astrostudio/` package.
   Nothing breaks; the MVP keeps running.
2. **Phase 2–3** port reflection/overrides into the `python-runtime` plugin machinery and
   express the three MVP nodes (SkyCoord, to_galactic, separation) as the `astropy`
   reference plugin with a real manifest. The MVP's hardcoded `default_library()` is
   replaced by "load providers from installed plugins".
3. **Phase 4** replaces `execute_direct`-in-GUI with submission to the `local-process`
   executor (same behavior, out-of-process); generated-script export remains.
4. **Phases 6–9** replace the in-memory `Graph` with the serializable workflow model
   and rebuild the GUI as a kernel-API client. `.astroproj` is superseded by the project
   directory format (a one-shot converter is provided).
5. When the astropy reference plugin reaches feature parity with the MVP (same three
   workflows runnable end-to-end via kernel + GUI), the `astrostudio/` package is
   removed. Parity is defined by the e2e test reproducing the README example outputs.

The MVP is never "big-bang rewritten"; it is hollowed out into a client + a plugin.

## 13. Open questions (tracked, not blocking Phase 1)

- Final project/product name and PyPI namespace (working name `smk` may collide;
  `metakernel` is taken by an existing Jupyter project).
- Registry hosting for the community index (static index over HTTPS is the Phase 5
  baseline; see REGISTRY.md §7 for candidate hosting models).
- Workflow language interop (CWL import/export?) — deferred until Phase 6 experience.
- Instrument safety interlocks standard (ROADMAP.md Phase 9).
