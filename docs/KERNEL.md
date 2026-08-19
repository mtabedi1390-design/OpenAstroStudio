# Kernel Specification

**Status:** Draft v0.1 · Companion to [ARCHITECTURE.md](ARCHITECTURE.md)

The kernel is the small, stable, domain-agnostic core. It owns the domain model, the
service contracts, the event bus, persistence, and lifecycle management. It contains
**no** scientific knowledge and **no** UI.

---

## 1. Kernel responsibilities (exhaustive)

The kernel does exactly eight things:

1. **Model** — define the domain nouns as pure, serializable data (§2).
2. **Host plugins** — validate, load, verify, quarantine (PluginHost, §3.2).
3. **Resolve capabilities** — find/compare providers, plan executions (CapabilityResolver, §3.1; details CAPABILITY_MODEL.md).
4. **Execute** — schedule workloads onto ExecutionProviders and track them (ExecutionFabric, §3.3; details EXECUTION_MODEL.md).
5. **Catalog data** — track Datasets/Artifacts and their storage (DataCatalog, §3.4; details DATA_MODEL.md).
6. **Record provenance** — persist a record for every execution (ProvenanceStore, §3.5; details PROVENANCE.md).
7. **Enforce policy** — mediate every side effect through permissions (PolicyEngine, §3.6; details SECURITY.md).
8. **Publish events** — typed pub/sub for loose coupling (EventBus, §4).

Anything not on this list belongs in a plugin, executor, registry, agent, or client.

## 2. Domain model

All model types live in `smk.kernel.model`, are frozen dataclasses (or pydantic-style
validated models — implementation detail), have JSON schemas, and never hold live
callables, sockets, or OS handles. **IDs, not object references**, connect entities.

```python
# smk/kernel/model/ — representative definitions (abridged)

@dataclass(frozen=True)
class Capability:
    id: str                    # "cap:coords/coordinate-transformation@1"
    name: str
    summary: str
    input_schema: SchemaRef    # JSON-schema of invocation inputs
    output_schema: SchemaRef
    tags: tuple[str, ...]      # search facets ("astronomy", "coordinates")
    docs_url: str | None

@dataclass(frozen=True)
class Provider:
    id: str                    # "provider:org.astropy.coordinates/skycoord-transform"
    plugin_id: str
    capability_id: str
    invocation: InvocationSpec # how to build a Workload (see EXECUTION_MODEL.md §3)
    requirements: Requirements # runtimes, platforms, resources, permissions
    quality: QualityHints      # precision/perf/maturity hints for comparison
    health_check: InvocationSpec | None

@dataclass(frozen=True)
class Plugin:                  # installed state of a plugin (manifest is the source)
    id: str                    # "plugin:org.astropy.coordinates@1.2.0"
    manifest: PluginManifest   # parsed, schema-validated (PLUGIN_SPEC.md)
    state: PluginState         # see §3.2
    trust: TrustLevel          # SECURITY.md §3
    install_path: Path

@dataclass(frozen=True)
class Environment:
    id: str                    # "env:python-venv/3f2a…"
    provider_type: str         # "python-venv" | "conda" | "docker-image" | "ssh-host" | …
    spec: Mapping[str, Any]    # executor-specific, schema'd by the executor
    state: EnvironmentState    # REQUESTED → PROVISIONING → READY → DEGRADED → RETIRED

@dataclass(frozen=True)
class Workflow:
    id: str
    nodes: tuple[WorkflowNode, ...]
    edges: tuple[WorkflowEdge, ...]   # (source_node, output_port) → (target_node, input_port)
    schema_version: int

@dataclass(frozen=True)
class WorkflowNode:
    id: str
    kind: NodeKind             # CAPABILITY | DATASET | VISUALIZATION | AGENT | INSTRUMENT
    capability_id: str | None  # for CAPABILITY nodes
    provider_pin: str | None   # optional: pin a specific provider
    params: Mapping[str, Any]  # literal params (validated against capability input_schema)

@dataclass(frozen=True)
class Execution:
    id: str                    # "exec:<uuid>"
    workload: Workload         # EXECUTION_MODEL.md §3
    state: ExecutionState      # EXECUTION_MODEL.md §5 state machine
    executor_id: str
    environment_id: str | None
    submitted_by: Principal    # user | agent:<id> | workflow:<id>
    provenance_id: str

@dataclass(frozen=True)
class Project:
    id: str
    root: Path                 # project directory (project.yaml + workflows/ + data refs)
    name: str
    default_registry: str | None
```

`Dataset`, `Artifact`, `SchemaRef`, `Unit`, `Resource` — DATA_MODEL.md.
`Instrument` is *not* a separate kernel noun at the contract level: it is a `Provider`
whose `requirements.runtimes` names an instrument executor and whose manifest declares
`instrument` permissions (SECURITY.md §4). `Service` likewise: a Provider whose
invocation targets a long-running endpoint. This keeps the kernel noun set minimal.

`Tool` is a manifest-level grouping (PLUGIN_SPEC.md §4): a named piece of software a
plugin integrates, to which its providers refer. The kernel stores it as metadata only.

`Agent` contracts — AGENT_MODEL.md. The kernel knows agents only as `Principal`s whose
API calls are policy-gated; agent orchestration lives outside the kernel.

## 3. Kernel services

Each service is defined by a Protocol in `smk.kernel.services.contracts`; the default
implementations are replaceable (principle: contracts over code).

### 3.1 CapabilityResolver

```python
class CapabilityResolver(Protocol):
    CONTRACT_VERSION = 1
    def search(self, query: CapabilityQuery) -> list[Capability]: ...
    def providers_for(self, capability_id: str) -> list[Provider]: ...
    def compare(self, provider_ids: Sequence[str]) -> ProviderComparison: ...
    def resolve(self, request: ResolutionRequest) -> ExecutionPlan: ...
    # raises ResolutionError(reason: NO_PROVIDER | NO_ENVIRONMENT | POLICY_DENIED |
    #                        DEPENDENCY_CONFLICT | AMBIGUOUS_REQUIRES_CHOICE)
```

Full pipeline (discover → select → plan) in CAPABILITY_MODEL.md §5.

### 3.2 PluginHost

```python
class PluginHost(Protocol):
    CONTRACT_VERSION = 1
    def install(self, source: PluginSource, *, trust: TrustLevel) -> Plugin: ...
    def uninstall(self, plugin_id: str) -> None: ...
    def load(self, plugin_id: str) -> Plugin: ...
    def health_check(self, plugin_id: str) -> HealthReport: ...
    def list(self, state: PluginState | None = None) -> list[Plugin]: ...
```

Plugin lifecycle state machine (persisted in StateStore):

```
DISCOVERED → FETCHED → VERIFIED → INSTALLED → LOADED → ACTIVE
                 │          │          │          │
                 └──────────┴──────────┴──────────┴──→ QUARANTINED(reason)
ACTIVE → DISABLED (user action, reversible) → UNINSTALLED
```

- `VERIFIED`: manifest schema-valid, signature/hash checks per trust level.
- `ACTIVE`: health check passed; only ACTIVE plugins contribute providers to resolution.
- `QUARANTINED`: any failure (bad manifest, failed health check, policy violation,
  crash on load). Quarantine never crashes the kernel; it emits `PluginQuarantined`.

### 3.3 ExecutionFabric

Façade over registered ExecutionProviders; owns the Execution state machine, the
executor registry, and workload↔executor matching. Contract in EXECUTION_MODEL.md §4.

### 3.4 DataCatalog / 3.5 ProvenanceStore

See DATA_MODEL.md and PROVENANCE.md. Kernel invariant: `ExecutionFabric` will not mark
an Execution `SUCCEEDED` until its artifacts are registered and its provenance record
is written (write-ahead: provenance skeleton is created at submission time).

### 3.6 PolicyEngine

Every service consults the PolicyEngine before side effects:

```python
class PolicyEngine(Protocol):
    CONTRACT_VERSION = 1
    def check(self, principal: Principal, action: Action, target: Target) -> Decision:
        ...  # Decision = ALLOW | DENY(reason) | REQUIRE_APPROVAL(request_id)
```

`REQUIRE_APPROVAL` suspends the operation and emits `ApprovalRequested`; clients (GUI/CLI)
present it to the user. See SECURITY.md §5.

## 4. Event bus

In-process, synchronous-dispatch pub/sub with a persistent, append-only log (StateStore
table `events`). Out-of-process clients receive events via the JSON-RPC service's
subscription stream.

```python
@dataclass(frozen=True)
class Event:
    id: str; type: str; time: datetime
    principal: Principal | None
    payload: Mapping[str, Any]      # schema'd per event type
    correlation_id: str | None      # e.g. execution id, plugin id
```

Core event types (extensible; namespaced `smk.*` for kernel, plugins use their own
namespace): `PluginInstalled`, `PluginQuarantined`, `CapabilityDiscovered`,
`EnvironmentCreated`, `EnvironmentDegraded`, `WorkflowStarted`, `WorkflowFinished`,
`ExecutionSubmitted`, `ExecutionStateChanged`, `ExecutionFailed`, `DatasetCreated`,
`ArtifactStored`, `AgentStarted`, `AgentFinished`, `ApprovalRequested`,
`ApprovalResolved`, `InstrumentConnected`, `InstrumentDisconnected`, `PolicyDenied`.

Rules:
- Handlers must not raise; a raising handler is unsubscribed and logged (bus stability).
- Events are facts, not commands. No component may implement behavior that *requires*
  another component to observe an event (loose coupling, not hidden RPC).
- The audit log (SECURITY.md §7) is a filtered view of the event log — same store.

## 5. Persistence and state management

| Store | Technology (default) | Contents |
|---|---|---|
| StateStore | SQLite via a `Repository` protocol (swappable) | plugins, environments, executions, grants, events, dataset/artifact metadata, registry cache |
| ArtifactStore | content-addressed files `~/.smk/store/sha256/<hex>` | immutable artifact payloads |
| Project files | plain directory, git-friendly | `project.yaml`, `workflows/*.workflow.json`, `datasets/*.dataset.json` (references, not payloads) |
| Config | `~/.smk/config.toml` | registries, default executors, policy defaults |

Rules:
- All schema'd documents carry `schema_version`; the kernel ships migrations
  (forward-only) for StateStore and converters for document formats.
- The kernel never stores secrets; credentials go to the OS keyring behind a
  `CredentialStore` protocol (SECURITY.md §6).
- Everything in a project directory must be diffable text — reproducibility and
  community collaboration depend on it.

## 6. Process model and the API façade

- **Library mode** (Phase 1): clients `import smk.api` in-process. Single-process,
  simplest, used by tests and notebooks.
- **Service mode** (Phase 1 as well, thin): `scientific kernel serve` runs the kernel
  as a local daemon exposing JSON-RPC 2.0 over a unix domain socket (Windows: named
  pipe), so GUI + CLI + agents share one state and one event stream. The RPC surface is
  generated from the same `smk.api` façade — one source of truth.
- Remote/multi-user deployment is explicitly out of scope until Phase 10; the API is
  designed not to preclude it (no client-side filesystem assumptions in the contract).

`smk.api` is the **only** supported entry point for clients. Its surface mirrors the
CLI verb structure:

```
api.capability: search / providers / compare / resolve
api.plugin:     install / uninstall / list / health / inspect
api.environment: list / create / retire
api.workflow:   validate / run / export_script / status
api.execution:  submit / status / logs / cancel / artifacts
api.dataset:    register / get / list
api.provenance: get / trace / reproduce_check
api.registry:   search / show / refresh
api.agent:      run / status / approve / deny        (Phase 7)
api.events:     subscribe / query
```

## 7. Kernel error taxonomy

```
SmkError
├── ResolutionError      (resolver; carries structured reason + candidates considered)
├── PluginError          (manifest invalid, load failure, health-check failure)
├── InstallError         (fetch/verify/dependency failures; always leaves system unchanged)
├── ExecutionError       (submission/runtime; execution record still persisted)
├── PolicyError          (DENY decisions surface as this; approval flows do not raise)
├── RegistryError        (index unreachable/corrupt; kernel degrades to cached index)
└── DataError            (schema mismatch, missing artifact, hash mismatch)
```

Every error carries: machine-readable `code`, human `message`, `correlation_id`,
and remediation hints where known. Errors cross the RPC boundary losslessly.

## 8. What the kernel must never do

- Import or special-case any scientific library.
- Execute plugin code in its own process by default (only the explicitly-trusted
  in-process fast path may, per SECURITY.md §3).
- Talk to the network except through RegistryClient and ExecutionProviders.
- Render UI, format for humans (clients' job), or embed an LLM (agents' job).
- Grow: new nouns require an ADR (architecture decision record in `docs/adr/`) showing
  the concept cannot be expressed as plugin/provider/executor/agent composition.

## 9. Testable contracts (Phase 1 gate)

- Model round-trip: every model type serializes → deserializes identically (golden files).
- Lifecycle: property-based tests that no illegal state transition is reachable
  (plugin and execution state machines).
- Event bus: raising handler is isolated; events persisted and replayable in order.
- Policy mediation: a test double PolicyEngine returning DENY blocks every side-effecting
  API path (checked by an exhaustive API-surface test).
- API/RPC parity: auto-test that every `smk.api` method is reachable and equivalent
  over JSON-RPC.
