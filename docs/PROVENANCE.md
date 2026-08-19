# Provenance & Reproducibility

**Status:** Draft v0.1 · Companion to [KERNEL.md](KERNEL.md), [DATA_MODEL.md](DATA_MODEL.md), [EXECUTION_MODEL.md](EXECUTION_MODEL.md)

Provenance is a **kernel-level concern**: every meaningful execution is recorded well
enough to answer *"How exactly was this result produced?"* and *"Can I reproduce it?"*
It is not an optional plugin feature and cannot be bypassed by clients or agents.

---

## 1. Model

One record per Execution, write-ahead (skeleton written at submission, completed at a
terminal state — a crash still leaves a truthful partial record):

```python
@dataclass(frozen=True)
class ProvenanceRecord:
    id: str                          # "prov:<execution-uuid>"
    schema_version: int
    execution_id: str
    # WHAT
    capability_id: str | None        # None for raw workload submissions
    provider_id: str | None
    plugin: PluginPin                # id + exact version + manifest hash
    workload_hash: str               # hash of the serialized Workload
    parameters: Mapping[str, Any]    # literal inputs (secret-redacted, §6)
    input_refs: tuple[DataRef, ...]  # dataset ids @ versions, artifact hashes, resources
    random_seeds: Mapping[str, int] | None   # when declared by the provider
    # WHERE / HOW
    executor: ExecutorPin            # id + version + descriptor hash
    environment: EnvironmentLock     # the locked env: exact packages/digests (EXECUTION_MODEL.md §7)
    hardware: HardwareInfo           # os, arch, cpu, gpu (best-effort), hostname hash
    kernel_version: str
    workflow_run: str | None         # enclosing workflow-run id + node id
    submitted_by: Principal          # user | agent-run id (AGENT_MODEL.md §7)
    # WHEN / RESULT
    timestamps: Timestamps           # submitted, started, finished
    state: ExecutionState            # terminal state
    error: ErrorInfo | None
    output_refs: tuple[DataRef, ...] # artifacts produced (hashes) + validated outputs
    resource_usage: Usage | None
```

Records are immutable, append-only, and stored in the ProvenanceStore (StateStore
tables + exportable JSON). Artifacts/datasets point back via `lineage` (DATA_MODEL.md).

## 2. Capture rules (normative)

- The ExecutionFabric writes provenance; executors and plugins **cannot opt out** —
  they only *add* detail (e.g. a provider declares its random-seed parameters in its
  manifest so the fabric records them; tools that manage seeds internally without
  declaring them are recorded as `random_seeds: None` — unknown, not falsely "seeded").
- `SUCCEEDED` is unreachable without a complete record (KERNEL.md §3.4 invariant).
- Environment locks are captured at environment **creation**, referenced (not copied)
  by each record.
- Workflow runs create a run-level record linking member execution records + the
  workflow document hash — the full graph story is reconstructible.
- Agent runs are provenance subjects too (AGENT_MODEL.md §7): plan, LLM identity,
  approvals.

## 3. Lineage queries

`api.provenance` supports:

- `get(execution_id)` — the record.
- `trace(data_ref)` — full ancestry DAG of an artifact/dataset version: which
  executions, from which inputs, recursively to leaves (resources/registered raw data).
- `descendants(data_ref)` — everything derived from a given input (impact analysis:
  "this calibration file was bad — what's affected?").
- `diff(exec_a, exec_b)` — structured difference of two records (parameters,
  environment lock, versions) — the "why do my results differ?" tool.

## 4. Reproducibility

Honest tiers, reported not assumed — `api.provenance.reproduce_check(execution_id)`
evaluates which tier is *currently possible* on this host:

| Tier | Meaning | Requirements |
|---|---|---|
| R0 — recorded | full record exists | always (by construction) |
| R1 — re-runnable | same workload can be resubmitted | provider installed, inputs present |
| R2 — environment-exact | run in an equivalently locked env | env lock satisfiable (packages/digests still obtainable) |
| R3 — bit-identical | outputs hash-equal | R2 + deterministic tool + seeds declared |

`scientific inspect <artifact>` shows the trace; `scientific run --reproduce <exec>`
re-executes at the highest achievable tier and **reports the achieved tier and output
hash comparison** — it never claims bit-identity it didn't verify (honesty rule).

## 5. Retention & export

- Records are small (payloads live in the CAS); default retention is "forever",
  user-configurable GC only for executions whose artifacts were deleted.
- Export: `scientific provenance export <exec>` emits a self-contained JSON bundle
  (record + ancestry + env locks). Format is documented and versioned; a mapping to
  **W3C PROV-O** is maintained for interoperability (open-standards principle) —
  export-only in early phases, not the internal model.

## 6. Privacy & secrets

Parameters are recorded **after** secret redaction: values sourced from the
CredentialStore are stored as `secret:<name>@<version-hash>` references, never
plaintext. Hostnames are hashed. Records shared via export get an additional
scrub pass (paths → relative, principal → pseudonym) with a `--redacted` flag.

## 7. Testable contracts (Phase 1 gate, extended each phase)

- Write-ahead: kill the kernel mid-execution → partial record exists and is truthful.
- Completeness: property test — every SUCCEEDED execution's record passes the record
  schema with no missing required fields.
- Lineage: build a 3-step chain, assert `trace` reconstructs the full DAG and
  `descendants` finds all derived artifacts.
- Reproduce: re-run the astropy reference execution, achieve R2, verify outputs
  hash-equal (it is deterministic ⇒ R3), and assert the reported tier matches.
- Redaction: a credential-using execution's record contains no secret bytes
  (scanned, not assumed).
