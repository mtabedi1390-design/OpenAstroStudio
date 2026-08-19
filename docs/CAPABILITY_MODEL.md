# Capability Model

**Status:** Draft v0.1 · Companion to [ARCHITECTURE.md](ARCHITECTURE.md), [KERNEL.md](KERNEL.md)

The capability model is the platform's first-class discovery and substitution mechanism:
tools advertise **what they can do** (Capabilities); users and agents request outcomes,
and the resolver selects **who does it** (Providers) and **where it runs** (Executions).

---

## 1. Definitions

### 1.1 Capability

A **Capability** is a versioned, schema-typed contract for a unit of scientific work.
It is pure interface — it names the operation and types its inputs/outputs; it says
nothing about implementation.

Authored as a document (in a plugin or a capability-namespace package):

```yaml
# capability document (JSON canonical; YAML authoring)
schema_version: 1
id: cap:coords/coordinate-transformation@1
name: Coordinate transformation
summary: Transform points between astronomical/geodetic reference frames.
tags: [coordinates, transformation]
input_schema:
  type: object
  required: [points, source_frame, target_frame]
  properties:
    points:        { $ref: "schema:coords/point-list@1" }   # dataset schema ref
    source_frame:  { type: string }
    target_frame:  { type: string }
output_schema:
  type: object
  required: [points]
  properties:
    points:        { $ref: "schema:coords/point-list@1" }
docs: ./docs/coordinate-transformation.md
conformance:                      # optional but strongly encouraged
  cases:
    - name: icrs-to-galactic-m31
      input:  { points: …, source_frame: icrs, target_frame: galactic }
      expect: { points: …, tolerance: 1e-6 }
```

Rules:
- **Namespaced**: `cap:<namespace>/<name>@<major>`. Namespaces are registry-governed
  (REGISTRY.md §5); `core/` is reserved for kernel-blessed generic capabilities
  (e.g. `core/tabular-transform`, `core/file-conversion`).
- **Versioned by major only** in the ID. Backward-compatible schema additions bump a
  `revision` field; breaking changes create `@2` (both can coexist).
- **Domain capabilities live in plugins/registries** — the kernel ships none except the
  `core/` generics. "coordinate_transformation" is astronomy/geodesy knowledge and is
  defined by the coords namespace owners, not by the kernel.
- **Conformance cases** make capabilities testable: any provider claiming the capability
  must pass them (within declared tolerances). This is what makes provider substitution
  trustworthy rather than nominal.

### 1.2 Provider

A **Provider** binds a Capability to a concrete implementation, declared in a plugin
manifest (PLUGIN_SPEC.md §5):

```yaml
providers:
  - name: skycoord-transform
    capability: cap:coords/coordinate-transformation@1
    tool: astropy                      # manifest-level Tool this uses
    invocation:                        # → Workload template (EXECUTION_MODEL.md §3)
      type: python-call
      entrypoint: smk_plugin_astropy.coords:transform
      marshalling: json                # how inputs/outputs cross the boundary
    requirements:
      runtimes: [ { type: python, version: ">=3.11", packages: ["astropy>=6"] } ]
      platforms: [linux, macos, windows]
      resources: { cpu: 1, memory_mb: 512 }
      permissions: []                  # pure computation: no fs/net/instrument perms
    quality:
      maturity: stable                 # experimental | beta | stable
      precision: reference             # provider-declared, comparison hint
      throughput_hint: "1e6 points/s single core"
    health_check: { type: python-call, entrypoint: smk_plugin_astropy.coords:health }
```

A provider is **only** visible to resolution when its plugin is `ACTIVE` and its
health check and conformance cases have passed in the current installation.

### 1.3 The same model for software, services, and instruments

| Backing implementation | invocation.type (EXECUTION_MODEL.md §3) | Example |
|---|---|---|
| Python callable | `python-call` | astropy transform |
| CLI executable | `process` | a C++ solver, an IRAF task via wrapper |
| Container | `container-run` | CASA task in an image |
| Long-running service | `service-call` | a lab compute service, DS9 via SAMP/XPA adapter |
| Hardware instrument | `instrument-op` | telescope slew, camera exposure |
| AI model | `service-call`/`python-call` | local inference model |

The capability layer is identical in all cases; only the invocation/executor differs.

## 2. Capability queries

```python
@dataclass(frozen=True)
class CapabilityQuery:
    text: str | None = None            # free text: "spectral analysis"
    tags: tuple[str, ...] = ()
    input_matches: SchemaRef | None = None   # find capabilities accepting this data
    output_matches: SchemaRef | None = None  # find capabilities producing this data
    namespace: str | None = None
```

`input_matches`/`output_matches` enable graph-building assistance: "what can I connect
to this dataset/port?" — the GUI's suggestion engine and agents both use this.

Search is served from the local index (installed plugins + cached registry indexes);
it works fully offline.

## 3. Provider comparison

`resolver.compare(provider_ids)` returns a structured, non-opinionated comparison —
the kernel ranks only on hard facts; soft preference is the caller's job:

```python
@dataclass(frozen=True)
class ProviderComparison:
    rows: list[ProviderFacts]

@dataclass(frozen=True)
class ProviderFacts:
    provider_id: str
    installable_here: bool          # platform + runtime resolvable on this host
    installed: bool
    environments_ready: list[str]   # env ids that can run it right now
    trust: TrustLevel
    maturity: str
    conformance: ConformanceStatus  # PASSED | FAILED(cases) | NOT_RUN
    quality: QualityHints           # provider-declared, displayed not trusted
    estimated_setup: SetupEstimate  # NONE | INSTALL_PACKAGES | BUILD_ENV | UNAVAILABLE
```

## 4. Resolution requests

```python
@dataclass(frozen=True)
class ResolutionRequest:
    capability_id: str
    inputs: Mapping[str, Any]            # validated against capability input_schema
    provider_pin: str | None = None      # explicit user/workflow choice wins
    constraints: Constraints = Constraints()

@dataclass(frozen=True)
class Constraints:
    require_local: bool = False          # never leave this machine
    max_setup: SetupEstimate = SetupEstimate.BUILD_ENV
    executor_types: tuple[str, ...] = () # restrict, e.g. ("docker",)
    deadline_s: float | None = None
    trust_floor: TrustLevel = TrustLevel.COMMUNITY
```

## 5. Resolution pipeline (normative)

Eleven steps, mapping to the kernel's required abilities. Each step has a defined
failure mode; the pipeline is a pure function of kernel state until step 8 (no side
effects before planning is done — critical for agent dry-runs).

```
1. DISCOVER capability      — id lookup / query; fail: ResolutionError(UNKNOWN_CAPABILITY)
2. DISCOVER providers       — ACTIVE plugins + (optionally) registry candidates
                              fail: NO_PROVIDER (report nearest registry matches)
3. FILTER by hard facts     — platform, trust_floor, constraints, policy pre-check
                              fail: NO_PROVIDER(after_filtering, reasons per provider)
4. COMPARE / SELECT         — provider_pin > single candidate > deterministic ranking
                              (installed > installable; conformance PASSED > NOT_RUN;
                              higher trust > lower; stable > beta). If ranking ties and
                              interactive=False → AMBIGUOUS_REQUIRES_CHOICE
5. INSPECT requirements     — runtimes, packages, resources, permissions of selection
6. RESOLVE dependencies     — delegate to the matching environment provider's solver
                              (pip/conda/image pull …); fail: DEPENDENCY_CONFLICT
7. SELECT environment       — reuse READY env satisfying requirements, else plan creation
                              fail: NO_ENVIRONMENT(requirements, candidates_rejected)
8. PLAN                     — emit ExecutionPlan (below); policy full check here;
                              REQUIRE_APPROVAL suspends, DENY → POLICY_DENIED
9. EXECUTE                  — fabric submits Workload (EXECUTION_MODEL.md)
10. MONITOR                 — state events, logs, heartbeats
11. COLLECT + RECORD        — artifacts registered, outputs schema-validated,
                              provenance completed (PROVENANCE.md)
```

```python
@dataclass(frozen=True)
class ExecutionPlan:
    request: ResolutionRequest
    provider_id: str
    steps: tuple[PlanStep, ...]   # e.g. CreateEnvironment, InstallPackages, RunWorkload
    workload: Workload            # fully materialized (EXECUTION_MODEL.md §3)
    executor_id: str
    approvals_required: tuple[ApprovalRequest, ...]
    estimated: SetupEstimate
```

Plans are serializable and inspectable — the CLI shows them (`scientific run --plan`),
agents must produce them for review, and the GUI renders them before consenting.

## 6. Capability evolution and compatibility

- Adding optional input fields: same major, `revision += 1`. Providers declare the
  minimum revision they implement.
- Removing/renaming fields or changing semantics: new major `@2`. Registries list both;
  resolution never silently crosses majors.
- A provider may claim multiple capabilities and multiple majors of one capability.
- Deprecation: capabilities carry `deprecated: {by: cap:…, note: …}` metadata surfaced
  in search results.

## 7. Anti-goals

- The kernel does not define scientific ontologies or "the" taxonomy of science.
  Namespaces evolve socially in registries; the kernel only enforces the contract format.
- No automatic cross-capability semantic inference ("this FFT is probably that FFT").
  Equivalence is only ever declared explicitly (`equivalent_to:` metadata) and verified
  by shared conformance cases.
- Ranking never encodes vendor preference; the deterministic order in step 4 is fully
  documented and overridable by `provider_pin`.

## 8. Testable contracts (Phase 2 gate)

- Capability documents: schema validation + golden round-trips.
- Resolver: table-driven tests for every failure mode in §5 (each `ResolutionError`
  reason constructible and asserted).
- Determinism: same kernel state + same request ⇒ identical plan (hash the plan).
- Conformance harness: `sdk` runner executes capability conformance cases against a
  provider in its environment; reference plugin (astropy) passes the
  `coordinate-transformation` cases matching the MVP's known-good outputs
  (M31: l=121.1706°, b=−21.5719°).
- Purity: steps 1–7 make no state changes (asserted with a mutation-detecting store).
