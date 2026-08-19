# Agent Model

**Status:** Draft v0.1 · Companion to [ARCHITECTURE.md](ARCHITECTURE.md), [SECURITY.md](SECURITY.md)

AI is a **controlled orchestration layer over the kernel** — not a chatbot bolted onto
the GUI, and not an unrestricted actor on the host. Agents are kernel clients: they act
through `smk.api`, under the PolicyEngine, with mandatory approval boundaries.

---

## 1. Position in the architecture

```
User Intent → Agent → Plan → Kernel Policy → Capability Resolver
            → Execution Fabric → Scientific Tools → Results → Validation → Provenance
```

- Agents live in `smk.agents` (orchestration runtime) — **outside** the kernel.
  The kernel knows agents only as `Principal`s (KERNEL.md §2).
- The platform is fully usable with no agent installed and no LLM configured.
  Agents are Phase 7; nothing earlier depends on them.

## 2. LLM provider abstraction (provider-agnostic, local-first)

```python
# smk/agents/llm.py
CONTRACT_VERSION = 1

class LLMProvider(Protocol):
    id: str                                  # "ollama", "llama-cpp", "openai", …
    def descriptor(self) -> LLMDescriptor: ...   # local|remote, models, tool-calling support
    def complete(self, request: ChatRequest) -> ChatResponse: ...
    def stream(self, request: ChatRequest) -> Iterator[ChatDelta]: ...
```

- Reference implementations: one **local** provider (OpenAI-compatible local endpoint —
  covers Ollama/llama.cpp/vLLM) and one cloud provider. Both behind the same contract;
  configured in `~/.smk/config.toml`; no API key ⇒ local-only, everything still works.
- Model/provider identity is recorded in agent provenance (§7).
- Remote LLM use is itself a **policy-controlled action**: sending data off-host
  requires a `net`-style grant (`llm.remote` permission), so "my data never leaves the
  machine" is enforceable, not aspirational.

## 3. Agent contract

```python
# smk/agents/contract.py
CONTRACT_VERSION = 1

class Agent(Protocol):
    id: str                          # "planner", "integration", …
    def descriptor(self) -> AgentDescriptor: ...
        # goals it accepts, api scopes it needs, risk class
    def propose(self, goal: Goal, ctx: AgentContext) -> AgentPlan: ...
    def execute_step(self, plan: AgentPlan, step_id: str, ctx: AgentContext) -> StepResult: ...

@dataclass(frozen=True)
class AgentPlan:                     # serializable, inspectable BEFORE anything runs
    goal: Goal
    steps: tuple[AgentStep, ...]     # each step = one typed kernel API call + rationale
    requires_approval: tuple[str, ...]   # step ids needing human consent
    predicted_effects: tuple[Effect, ...] # installs, executions, artifacts, net access

class AgentContext(Protocol):        # the ONLY tools an agent gets
    api: KernelApi                   # scope-limited smk.api facade (per grants)
    llm: LLMProvider
    memory: AgentMemory              # per-run scratch state, persisted with the run
    def ask_user(self, question: Question) -> Answer: ...   # routed to client via events
```

Key rules:
- **Plan-then-act.** `propose()` has read-only API access (resolver dry-runs, searches,
  inspections). Side effects happen only in `execute_step`, only for steps in an
  approved plan.
- **Typed steps, not shell.** Steps are kernel API calls (`plugin.install`,
  `workflow.run`, `environment.create` …). There is no generic "run arbitrary command"
  step; an agent that needs computation submits a Workload like any other client, going
  through the same executor isolation and policy.
- Agents are registered like executors (separate contract, deeper trust review — not
  the plugin mechanism; PLUGIN_SPEC.md §7).

## 4. Approval boundaries (mandatory)

Risk classes drive defaults (user-configurable per project, SECURITY.md §5):

| Action class | Default |
|---|---|
| Read/search/inspect/dry-run resolve | auto-allowed |
| Execute installed provider locally on project data | auto-allowed, logged |
| Create environment / install packages or plugins | **approval required** |
| Network access; remote execution; remote LLM | **approval required** |
| Write outside project dirs; credential use; instrument ops | **approval required** |
| Publish (registry), delete data, modify plugins | **approval required, per-item** |

Approvals are `ApprovalRequested` events carrying the plan step and predicted effects;
resolutions (`approve`/`deny`/`always-for-this-project`) are persisted grants. An
agent can never approve its own request; grants name a human principal.

## 5. Initial agent set

Small and honest — each ships only when it truly works end-to-end:

1. **WorkflowAgent** (first): goal → capability search → dry-run resolution → proposed
   Workflow → (approval) → run → validated, provenance-linked result. Exercises the
   whole stack with zero self-modification risk.
2. **EnvironmentAgent**: diagnose/repair environment issues via executor APIs
   ("why can't this provider run here?" → remediation plan).
3. **IntegrationAgent** (§6): the self-extension workflow.

PlannerAgent/ResearchAgent/DebugAgent/DocumentationAgent etc. from the vision are later
specializations of the same contract; they are not claimed until implemented.

## 6. Controlled self-extension (IntegrationAgent)

Goal: *"Integrate this scientific application"* — as a controlled development workflow,
never as autonomous host modification.

```
1. INSPECT     docs/CLI/API of the target (fetch requires net approval)
2. DRAFT       capability docs + plugin manifest + adapters (files in a sandbox
               plugin workspace, dev-mode dir — never in kernel or host paths)
3. TEST        run PluginContractTests + generated conformance cases via the SDK
               (executions go through normal executors/policy)
4. REVISE      iterate on failures (bounded retries)
5. PRESENT     human reviews: manifest, permissions requested, test results, diffs
6. APPROVE     human approves install as local-dev trust plugin
7. PACKAGE     .smkplugin archive
8. PROPOSE     registry submission (REGISTRY.md §6) — always a human-gated step
```

Invariants: generated plugins pass the **same** contract tests as human-written ones
(one quality bar); requested permissions are minimal and shown at approval; the agent
cannot raise a plugin's trust level; every generated artifact is provenance-linked to
the agent run that produced it.

## 7. Agent provenance & audit

Every agent run records: agent id/version, LLM provider+model identity, the goal, the
full approved plan, each step's API call + result, approvals with approver identity,
and links to all executions/artifacts/plugins produced. Stored in the ProvenanceStore
like any execution (PROVENANCE.md §5) and surfaced in the audit log. Answerable:
*"which of my results involved AI, doing what, approved by whom?"*

## 8. Failure modes

- LLM unavailable → agent runs fail cleanly (`AgentError(LLM_UNAVAILABLE)`); the rest
  of the platform is unaffected.
- Plan drift (a step's precondition no longer holds) → step fails, plan is re-proposed;
  agents never improvise unapproved steps.
- Runaway control: per-run budgets (max steps, max executions, max LLM calls,
  wall-clock) enforced by the agent runtime; exceeding one is a terminal failure.
- Denied approval → plan halts; partial effects remain visible and provenance-linked
  (no hidden rollback of real side effects).

## 9. Testable contracts (Phase 7 gate)

- Contract tests with a **scripted fake LLM** (deterministic transcripts): plan
  proposal, approval gating (side effect blocked without approval — exhaustive over
  step types), budget enforcement, drift handling.
- Policy: agent principal with no grants can read but cannot install/execute/net.
- WorkflowAgent E2E on the astropy reference plugin with the fake LLM; optional live
  local-LLM smoke test (non-blocking CI lane).
- IntegrationAgent E2E: generates a plugin for a tiny known CLI tool in-repo, passes
  PluginContractTests, requires and respects each approval step.
