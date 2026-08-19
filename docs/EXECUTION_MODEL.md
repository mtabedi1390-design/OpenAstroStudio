# Execution Model

**Status:** Draft v0.1 · Companion to [ARCHITECTURE.md](ARCHITECTURE.md), [KERNEL.md](KERNEL.md), [CAPABILITY_MODEL.md](CAPABILITY_MODEL.md)

The execution fabric answers: *"Where can this workload run, and what happened when it
did?"* It is an extensible provider architecture — the kernel hard-codes **no**
environment type.

---

## 1. Concepts

- **Workload** — a serializable description of one unit of work (what to run, with what
  inputs, needing what runtime). Produced by the resolver from a provider's invocation
  spec; never contains live objects.
- **ExecutionProvider (executor)** — a component that can prepare environments and run
  workloads somewhere (local process, venv, WSL, Docker, SSH, Slurm, K8s, cloud,
  instrument bus…). Executors are infrastructure extensions with their own contract —
  deliberately *not* plugins (PLUGIN_SPEC.md §7).
- **Environment** — a concrete prepared place a workload can run (a venv, a container
  image + runtime, an SSH host, a conda env). Owned/described by its executor.
- **Execution** — one run of one workload: state machine, logs, artifacts, provenance.

## 2. Honesty rule

The kernel ships with only what actually works. Phase 4 implements exactly two
executors — `local-process` and `python-venv` — and the contract + conformance suite
that all future executors (docker, wsl, ssh, slurm, …) must pass **before being
claimed**. The roadmap (ROADMAP.md) adds each executor only when its integration tests
run in CI (or, where CI cannot host it, behind an explicit `verified-manually` flag
surfaced to users).

## 3. Workload

```python
@dataclass(frozen=True)
class Workload:
    id: str
    invocation: Invocation            # discriminated union, below
    inputs: Mapping[str, InputBinding]    # literal | dataset:<id> | artifact:<hash>
    output_schema: SchemaRef
    requirements: Requirements        # runtimes / platforms / resources / permissions
    limits: Limits                    # timeout_s, max_memory_mb, max_disk_mb
    idempotency_key: str | None       # dedupe retries (KERNEL.md failure philosophy)

# Invocation kinds (each with a JSON schema; extensible via executor contract majors):
# python-call    {entrypoint, marshalling}          — run via SDK runner in a python env
# process        {argv_template, stdin?, cwd?, env?, output_map}   — an executable
# container-run  {image, command, mounts, output_map}
# service-call   {endpoint_ref, method, payload_template}          — long-running service
# instrument-op  {instrument_ref, operation, params}               — hardware op
```

`InputBinding` resolves to bytes/paths at staging time; large data moves by reference
and content hash, not by value (DATA_MODEL.md §6).

## 4. ExecutionProvider contract

```python
# smk/execution/contract.py
CONTRACT_VERSION = 1

class ExecutionProvider(Protocol):
    id: str                      # "local-process", "python-venv", "docker", …
    def descriptor(self) -> ExecutorDescriptor: ...
    # Capability negotiation — "where can this run?"
    def can_run(self, workload: Workload) -> Compatibility: ...
        # Compatibility = YES(env_ready: list[str]) | YES_WITH_SETUP(plan) | NO(reason)
    # Environment management (see §7)
    def create_environment(self, spec: EnvironmentSpec) -> Environment: ...
    def inspect_environment(self, env_id: str) -> EnvironmentStatus: ...
    def retire_environment(self, env_id: str) -> None: ...
    # Execution
    def submit(self, workload: Workload, env_id: str, ctx: SubmissionContext) -> str: ...
    def status(self, submission_id: str) -> ExecutionStatus: ...   # state + heartbeat
    def logs(self, submission_id: str, *, follow: bool = False) -> Iterator[LogChunk]: ...
    def cancel(self, submission_id: str) -> None: ...
    def collect(self, submission_id: str) -> CollectedResult: ...  # outputs + artifacts + usage

@dataclass(frozen=True)
class ExecutorDescriptor:
    id: str; contract_version: int
    invocation_types: tuple[str, ...]   # which Invocation kinds it accepts
    platforms: tuple[str, ...]
    isolation: IsolationLevel           # NONE | PROCESS | CONTAINER | REMOTE (SECURITY.md §4)
    verified: Verification              # CI | MANUAL | UNVERIFIED — honesty surfaced in UI/CLI
```

The **ExecutionFabric** (kernel) holds the executor registry, fans `can_run` out to all
registered executors to answer "where can this run?", enforces policy before `submit`,
persists state transitions, emits events, and applies timeouts/retries. Executors stay
dumb about policy and provenance — the fabric owns cross-cutting concerns.

## 5. Execution state machine

```
PENDING ──submit──▶ STAGING ──▶ RUNNING ──▶ COLLECTING ──▶ SUCCEEDED
   │                   │           │             │
   │                   │           ├──▶ CANCELLING ──▶ CANCELLED
   │                   ▼           ▼             ▼
   └────────────────▶ FAILED(reason) ◀───────────┘
                       reason ∈ { STAGING_ERROR, RUNTIME_ERROR, TIMEOUT,
                                  RESOURCE_EXCEEDED, LOST (heartbeat), POLICY_KILLED,
                                  COLLECT_ERROR, OUTPUT_SCHEMA_MISMATCH }
```

Rules:
- Terminal states: `SUCCEEDED`, `FAILED`, `CANCELLED`. No transitions out; retries
  create a **new** Execution referencing the old one (`retry_of`), same
  `idempotency_key`.
- Heartbeats: executors report liveness; the fabric marks silent executions
  `FAILED(LOST)` after `3 × heartbeat_interval` and attempts best-effort cleanup.
- `SUCCEEDED` requires: outputs validate against `output_schema`, artifacts registered,
  provenance record complete (KERNEL.md §3.4 invariant). Otherwise
  `FAILED(OUTPUT_SCHEMA_MISMATCH | COLLECT_ERROR)` — a run that "worked" but can't be
  trusted/reproduced is a failure.
- Every transition is an `ExecutionStateChanged` event and a StateStore row (crash
  recovery replays from the log; on kernel restart, non-terminal executions are
  re-polled or marked LOST).

## 6. Where code runs (isolation baseline)

- Workloads run **outside the kernel process** by default: `local-process` spawns a
  subprocess; `python-venv` spawns the venv's interpreter running the SDK runner.
- The only in-kernel-process execution is the explicitly-opted-in trusted fast path
  for `local-dev` plugins (SECURITY.md §4) — the migrated equivalent of the MVP's
  `execute_direct`, now a conscious policy decision instead of the default.
- Filesystem contract per execution: a fresh scratch `workdir`; staged read-only
  inputs; declared dataset/artifact paths; nothing else granted by default
  (enforcement strength depends on the executor's `IsolationLevel`; the descriptor
  never overstates it).

## 7. Environments and dependency management

Each executor owns an **environment provider** side:

```yaml
# EnvironmentSpec examples (executor-specific, schema'd)
- type: python-venv
  python: ">=3.11"
  packages: ["astropy>=6", "numpy>=2"]
  index_policy: default          # locked resolution recorded on creation
- type: docker-image             # (future executor)
  image: "casa:6.5"
  digest: "sha256:…"
```

The "install pipeline" from the vision maps to: resolver step 6 (RESOLVE dependencies)
delegates to the executor's solver; `create_environment` materializes it; the created
Environment stores the **locked** result (exact versions, hashes, image digests) —
this lock is what provenance references, making environments reproducible.
Environments are reused across executions when their lock satisfies a workload's
requirements; `retire_environment` garbage-collects.

## 8. Workflow execution

The workflow scheduler (kernel, Phase 6) compiles a `Workflow` into executions:
topological order (the MVP's proven approach, generalized), one Execution per
CAPABILITY node, edges become `InputBinding`s referencing upstream outputs/artifacts.
Node failures follow policy: `fail-fast` (default) or `continue-independent-branches`.
A workflow run is itself recorded (`WorkflowStarted`/`Finished`, run id in provenance
of every member execution). Nodes may resolve to different executors within one
workflow — this is the "Dataset → CASA → Python → GPU" story, expressed without any
of those words appearing in the kernel.

## 9. Executor conformance suite

`tests/execution/conformance/` runs against any executor (Phase 4 artifact):
happy path per supported invocation type; timeout kill; cancellation; resource-limit
enforcement (or declared non-enforcement); heartbeat loss simulation; scratch-dir
isolation; environment create/lock/reuse/retire; log streaming; collected artifacts'
hashes match staged reality. An executor is only listed as supported when this suite
passes for it in CI (§2).

## 10. Testable contracts (Phase 4 gate)

- State machine property tests: no illegal transition reachable; crash-replay
  reconstructs identical state.
- `local-process` + `python-venv` pass the conformance suite on linux/macos/windows CI.
- Idempotency: duplicate submit with same key returns the existing execution.
- Fabric policy mediation: DENY blocks submit; REQUIRE_APPROVAL suspends staging.
- End-to-end: astropy reference plugin runs in a freshly created venv environment and
  reproduces the MVP's known-good coordinate results.
