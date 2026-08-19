# Roadmap

**Status:** Draft v0.1 · Companion to [ARCHITECTURE.md](ARCHITECTURE.md) (see §12 there for MVP migration detail)

Rules that govern this roadmap:

1. **Each phase ships a usable artifact** — something a user or developer can actually
   run, not scaffolding.
2. **Nothing is claimed before it works** — an executor/integration/agent appears in
   docs and UI only when its conformance/contract tests pass in CI (EXECUTION_MODEL.md §2).
3. **No subsystem merges without contract tests** (see Testing Strategy, §T).
4. **The kernel stays small** — phase work lands as plugins/executors/clients wherever
   possible; kernel additions need an ADR.

---

## Phase 0 — Architecture & specifications *(this PR)*

**Artifact:** the `docs/` specification set; internally consistent contracts,
identities, lifecycles, failure modes, and this plan.
**Done when:** specs reviewed/merged; open questions tracked in ARCHITECTURE.md §13.

## Phase 1 — Minimal Scientific Kernel

**Scope:** `src/smk/kernel` (model, StateStore/SQLite, EventBus, PolicyEngine skeleton
with default-deny + grants, ProvenanceStore write-ahead, error taxonomy), `smk.api`
library mode + thin JSON-RPC service mode, minimal CLI (`kernel serve`, `events`,
`policy list`). The existing `astrostudio/` app keeps working untouched.
**Artifact:** an importable, servable kernel with persisted state/events and passing
Phase 1 test gates (KERNEL.md §9, PROVENANCE.md §7, SECURITY.md §11 subsets).

## Phase 2 — Capability model

**Scope:** capability/schema document formats + validation, local capability index,
CapabilityResolver steps 1–8 (planning; execution arrives in P4 — plans are inspectable
now), provider comparison, `scientific discover|inspect` against locally-registered
documents; DATA_MODEL core schemas + CAS artifact store.
**Artifact:** author a capability doc + provider entry, search it, get a deterministic
`ExecutionPlan` (dry-run) with structured failure reasons.
**Gate:** CAPABILITY_MODEL.md §8; DATA_MODEL.md §8.

## Phase 3 — Plugin SDK

**Scope:** manifest schema + verification, PluginHost lifecycle (install/quarantine/
rollback/dev-mode), SDK runtime + runner, `PluginContractTests`, reference plugins
`python-runtime` (migrated MVP reflection/overrides) and `astropy`.
**Artifact:** `scientific plugin new|dev|test|install`; the astropy plugin installs,
health-checks, and its providers appear in `discover`.
**Gate:** PLUGIN_SPEC.md §10.

## Phase 4 — Execution provider framework

**Scope:** ExecutionFabric + state machine + heartbeats/retries, executor contract +
conformance suite, `local-process` and `python-venv` executors (env create/lock/reuse),
resolver steps 9–11 live, provenance completed end-to-end.
**Artifact:** `scientific run cap:coords/coordinate-transformation@1 …` executes the
astropy provider in a freshly built, locked venv and records full provenance
reproducing the MVP's known-good results (R2/R3 verified).
**Gate:** EXECUTION_MODEL.md §10; PROVENANCE.md §7 reproduce test.
**Note:** Docker/WSL/SSH/Slurm/K8s/cloud executors are *not* in this phase and not
claimed; each lands individually later against the same conformance suite (P10).

## Phase 5 — Registry

**Scope:** index format, `RegistryClient`, `file://` + static-HTTPS implementations,
signing/hash verification, local cache, `discover/show/fetch` against a registry,
publication pipeline runnable locally (`scientific plugin publish --to file://…`).
**Artifact:** a git-repo registry hosting the reference plugins; a second machine
installs astropy-coordinates from it offline-verified.
**Gate:** REGISTRY.md §9.

## Phase 6 — Project & workflow system

**Scope:** project directory format, serializable Workflow + validation (schema-based
port compatibility), topological scheduler over the fabric, workflow-level provenance,
`scientific workflow validate|run|export-script`, `project verify`.
**Artifact:** the MVP's M31 example as a `.workflow.json`: validated, executed across
the fabric, reproducible, exportable as a transparent Python script (the MVP codegen
idea, now policy-safe).
**Gate:** workflow serialization round-trips; E2E parity test with MVP outputs;
scheduler failure-policy tests.

## Phase 7 — AI orchestration

**Scope:** LLMProvider contract + local & cloud implementations, agent contract +
runtime (plan/approve/budget), approval flow through clients, WorkflowAgent and
EnvironmentAgent; IntegrationAgent behind a feature flag until its E2E gate passes.
**Artifact:** with a local LLM (no paid API), "compute galactic coordinates of M31"
becomes a proposed, approved, executed, provenance-linked workflow.
**Gate:** AGENT_MODEL.md §9.

## Phase 8 — Scientific software integrations

**Scope:** `cli-runtime` plugin machinery; 2–3 real integrations chosen for diversity,
e.g. a CLI tool (process invocation), a second Python library, and one service-style
integration — each with conformance cases and contract tests; IntegrationAgent
un-flagged once it can regenerate one of them passing the same tests.
**Artifact:** genuinely heterogeneous workflows (Python + CLI + service) in one graph.

## Phase 9 — GUI as kernel client + instruments

**Scope:** new GUI (workspaces per vision §14) speaking only `smk.api`/JSON-RPC —
graph editor, capability browser, plan/approval dialogs, provenance viewer;
`instrument-op` invocation + one real reference instrument integration (e.g. a
serial/USB device such as an Arduino-class sensor) with interlock/approval policy.
**Artifact:** the platform usable end-to-end without touching a terminal; the legacy
`astrostudio/` GUI removed after parity tests pass (ARCHITECTURE.md §12 step 5).

## Phase 10 — Distributed execution

**Scope:** executors beyond local, added one at a time against the conformance suite —
priority order: Docker → WSL → SSH → Slurm; remote artifact staging; `CONTAINER`
isolation becomes real (SECURITY.md §4).
**Artifact:** the same workflow runs unmodified locally and in Docker/SSH targets,
provenance recording where it ran.

## Phase 11 — Community ecosystem

**Scope:** hosted registry service (accounts, publishing, web browse), publisher
verification, plugin developer docs site, governance (namespace policy, ADR process
public), TUF-style registry hardening.
**Artifact:** an external developer publishes a working plugin without talking to us.

---

## §T Testing strategy (cross-phase, normative)

| Layer | What | Examples / gates |
|---|---|---|
| Unit | pure logic, model round-trips | KERNEL.md §9 |
| Contract | every Protocol has a reusable conformance suite run against ALL implementations | executor suite (EXECUTION_MODEL.md §9), `PluginContractTests` (PLUGIN_SPEC.md §8), RegistryClient suite, LLMProvider fake |
| Integration | subsystem pairs (resolver+host, fabric+store) | resolver failure-mode table (CAPABILITY_MODEL.md §8) |
| Execution | real workloads in real envs in CI (linux/macos/windows) | astropy E2E (P4) |
| Security | default-deny exhaustive, redaction scanners, tamper suite, isolation probes | SECURITY.md §11 |
| Serialization | golden files for every document format; cross-version migration tests | schema_version converters |
| Compatibility | old manifests/documents against new kernel (N−1 majors) | PLUGIN_SPEC.md §6 |
| E2E | discover → install → connect → run → inspect → reproduce, per phase | P4/P6/P7 artifacts |

Enforcement:
- **No subsystem merges without its contract tests** — CI blocks on the phase gates
  listed above.
- Reference scientific integrations (astropy from P3; CLI tool from P8) are permanent
  CI fixtures — "tiny real science" over mocks wherever practical.
- GUI work (P9) builds only on API paths already covered by earlier gates.
- Property-based tests for state machines (plugin, execution) live from P1/P4 onward
  and run on every PR.
