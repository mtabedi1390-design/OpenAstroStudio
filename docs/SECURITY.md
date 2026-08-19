# Security Model

**Status:** Draft v0.1 · Companion to [KERNEL.md](KERNEL.md), [PLUGIN_SPEC.md](PLUGIN_SPEC.md), [AGENT_MODEL.md](AGENT_MODEL.md)

The platform will execute third-party scientific software and AI-generated code.
Baseline assumptions: **plugins are untrusted**, **agents are untrusted**, **the
registry can be compromised**, and the user's host and data must survive all three.

---

## 1. Principals, actions, targets

Every side effect is a `(principal, action, target)` triple checked by the PolicyEngine
(KERNEL.md §3.6):

- **Principals**: `user:<local>`, `agent:<run-id>`, `plugin:<id>` (as workload origin),
  `workflow:<run-id>`, `system`.
- **Actions** (closed kernel enum, extended only with contract majors):
  `fs.read`, `fs.write`, `net.connect`, `exec.submit`, `env.create`, `plugin.install`,
  `plugin.trust`, `credential.use`, `instrument.operate`, `registry.publish`,
  `data.delete`, `llm.remote`.
- **Targets**: path patterns, host patterns, executor ids, instrument ids,
  credential names.

Decisions: `ALLOW`, `DENY(reason)`, `REQUIRE_APPROVAL` → interactive consent that can
persist as a **grant** (scoped: once / session / project / always). Grants are stored
in the StateStore, listable and revocable (`scientific policy list|revoke`).

## 2. Permission model (declared, defaulted-deny)

Plugins declare needed permissions in their manifest (PLUGIN_SPEC.md §2); undeclared ⇒
denied. Declared ⇒ *requestable*, granted per policy at install/run time — declaration
is necessary, never sufficient.

```yaml
permissions:
  - fs:  { read: ["$DATASET", "$SCRATCH"], write: ["$SCRATCH", "$ARTIFACTS"] }
  - net: { hosts: ["archive.stsci.edu:443"] }        # explicit hosts, no wildcards by default
  - instrument: { ids: ["instrument:mycam"], ops: ["expose"] }
  - credential: { names: ["archive-token"] }
```

`$DATASET`/`$SCRATCH`/`$ARTIFACTS` are execution-scoped path variables — plugins
request *roles*, not raw host paths. Pure-computation plugins declare `permissions: []`
and get exactly scratch + staged inputs.

## 3. Trust levels

| Level | Source | Verification | Default posture |
|---|---|---|---|
| `core` | ships with the platform | repo CI + release signing | in-process allowed where needed |
| `verified` | registry, verified publisher | signature + registry review + contract tests | isolated execution, perms per grant |
| `community` | registry, unreviewed | hash + contract tests | isolated, every permission needs approval |
| `local-dev` | local directory (dev mode) | none — user's own code | isolated by default; user may enable trusted fast path per project |
| `unknown` | sideloaded archive/git | hash only | install requires explicit `--trust-unknown`, everything needs approval |

Trust levels only move **down** automatically (e.g. failed signature ⇒ quarantine).
Raising trust is a human action; agents can never do it (AGENT_MODEL.md §6).

## 4. Sandboxing & isolation (honest tiers)

Isolation is provided by **executors** and reported truthfully via
`ExecutorDescriptor.isolation` (EXECUTION_MODEL.md §4) — the UI/CLI display it; the
platform never claims stronger isolation than the executor delivers:

| IsolationLevel | Means | Phase 4 reality |
|---|---|---|
| `NONE` | in-kernel-process (trusted fast path only) | opt-in for core/local-dev |
| `PROCESS` | subprocess, scoped workdir, env-var scrubbing, resource limits (OS-dependent), **no OS-enforced fs/net barrier** | `local-process`, `python-venv` |
| `CONTAINER` | container boundary, mount whitelist, network namespace | when the docker executor lands (with its conformance suite) |
| `REMOTE` | separate host boundary | ssh/slurm executors, later |

Consequence (stated plainly in docs and UI): in early phases, `PROCESS` isolation is a
*policy* boundary, not a *security* boundary against actively malicious code. The
mitigation until `CONTAINER` lands is trust + approval gating (§§2–3), not pretense.
Strengthening `PROCESS` (seccomp/AppArmor on Linux, sandbox-exec on macOS, AppContainer
on Windows) is tracked on the roadmap as hardening work, claimed only when tested.

## 5. Approval workflow

`REQUIRE_APPROVAL` decisions emit `ApprovalRequested` with full context: principal,
action, target, originating plan/plugin/manifest excerpt, predicted effects. Clients
render consent UI (GUI dialog / CLI prompt / non-interactive ⇒ deny). Resolutions are
audited grants (§1). Agent-specific defaults: AGENT_MODEL.md §4. Headless/CI mode uses
pre-provisioned grant files — explicit, reviewable, no interactive bypass.

## 6. Credential isolation

- Secrets live in the OS keyring behind the `CredentialStore` protocol; the StateStore
  and all documents hold **names**, never values.
- Workloads receive credentials only if declared in the manifest **and** granted, injected
  by the executor at spawn (env var or file with scratch lifetime), scrubbed from logs.
- Provenance stores redacted references (PROVENANCE.md §6). Agents never see raw
  secret values — `credential.use` grants pass by name through the API.

## 7. Audit log

A filtered, append-only view of the event log (KERNEL.md §4): every policy decision
(incl. ALLOW of sensitive actions), grant creation/revocation, plugin trust changes,
install/uninstall, agent approvals, instrument operations, credential uses.
`scientific policy audit` queries it; it is exportable and covered by the same
retention rules as provenance.

## 8. Registry & supply-chain

- Plugin archives: sha256 manifest of contents + detached signature (verified levels).
  Index signing and mirror trust: REGISTRY.md §7.
- Installation never runs code from the archive during verification (manifest parsing
  is pure); health checks run **after** install, inside normal executor isolation.
- Version pinning + lockfiles at the environment level (EXECUTION_MODEL.md §7) limit
  silent upgrades.

## 9. AI safety boundaries (summary; normative text in AGENT_MODEL.md)

- Agents act only through scope-limited API facades; no shell/step escape hatch.
- Plan-then-approve for all effectful action classes; budgets bound runaway loops.
- Remote LLM data egress is a permission (`llm.remote`), denied by default.
- Generated plugins enter at `local-dev` trust maximum, pass the same contract tests,
  and require human approval to install, publish, or elevate.

## 10. Threats explicitly deferred

Multi-user kernels, network-exposed kernel API, tenant isolation, and registry
account-takeover response are out of scope until the phases that introduce them
(ROADMAP.md); the single-user local design must simply not preclude them.

## 11. Testable contracts (Phase 1 gate, extended each phase)

- Default-deny: undeclared permission ⇒ denied for every action type (exhaustive).
- Grant scoping: once/session/project grants expire/apply exactly as scoped; revocation
  takes effect on the next check.
- Path roles: a `process` workload observes staged inputs + scratch only (test probe
  attempts escapes; assert failures where the isolation level enforces, and assert the
  *reported* isolation level matches observed behavior — no overstatement).
- Credential flow: value reaches the workload, never the StateStore, logs, events, or
  provenance (scanners in CI).
- Quarantine: tampered archive (hash mismatch), permission-superset manifest, and
  failing health check each ⇒ QUARANTINED without kernel disruption.
- Audit completeness: every sensitive action in a scripted scenario appears in the
  audit log exactly once.
