# Registry Architecture

**Status:** Draft v0.1 · Companion to [PLUGIN_SPEC.md](PLUGIN_SPEC.md), [CAPABILITY_MODEL.md](CAPABILITY_MODEL.md), [SECURITY.md](SECURITY.md)

The registry answers capability-level search — *"spectral analysis"*, not *"which
package has the function?"* — and distributes plugins. It is conceptually
pip + conda + Docker Hub + scientific catalogs **at the capability level**, and it must
remain **replaceable**: the kernel is never coupled to one server.

---

## 1. Decoupling: protocol, not server

The kernel knows only the `RegistryClient` contract; a "registry" is anything that
serves the registry index format. Multiple registries are configured simultaneously
(like package-manager channels), with deterministic precedence:

```toml
# ~/.smk/config.toml
[[registry]]
name = "community"
url  = "https://registry.example.org/index"
priority = 10

[[registry]]
name = "lab-internal"
url  = "file:///shared/smk-registry"       # a static directory IS a valid registry
priority = 20                              # higher wins on id conflicts
```

```python
class RegistryClient(Protocol):
    CONTRACT_VERSION = 1
    def refresh(self) -> IndexSnapshot: ...          # fetch + verify index
    def search(self, query: RegistryQuery) -> list[RegistryEntry]: ...
    def show(self, plugin_id: str, version: str | None) -> RegistryEntry: ...
    def fetch(self, plugin_id: str, version: str) -> PluginArchive: ...
    def publish(self, archive: PluginArchive, auth: CredentialRef) -> PublishReceipt: ...
```

## 2. Index format (the real contract)

The index is a signed, versioned, **static-file-servable** document tree — a plain
directory or object store is a fully functional registry (no mandatory server code):

```
index/
├── index.json                 # {schema_version, generated_at, shards, signature}
├── capabilities/<ns>.json     # capability docs + which plugins provide them
├── plugins/<id>/versions.json # per-version: manifest, hashes, sig, compat, yanked flag
└── archives/…                 # .smkplugin files (or external URLs + hashes)
```

Entries carry, per the vision: identity/version, capabilities, providers, dependencies,
compatibility (kernel contract, platforms), documentation links, examples, security
metadata (hashes, signatures, publisher, trust events, yanks), verification info
(contract-test results, conformance results, §6), and installation recipes
(environment requirements surfaced pre-install).

## 3. Search

`scientific discover "spectral analysis"` searches **capabilities first**: matches
capability names/tags/summaries, then shows providers and their plugins, comparison
facts (CAPABILITY_MODEL.md §3), and install estimates. Plugin-name search exists but
is secondary. All search runs against the **local cached snapshot** — offline-first;
`refresh` is explicit or scheduled. Cache is per-registry with recorded snapshot ids
(which also enter provenance for installs: you can know *which index state* an install
decision came from).

## 4. Dependency semantics

Registry-level dependencies are **plugin → plugin** (and plugin → kernel contract)
only. Package-level dependencies (pip/conda/images) are resolved by environment
providers at install/run time (EXECUTION_MODEL.md §7) — the registry records them as
requirements, it does not solve them. Conflict policy: multiple installed plugins may
require different tool versions because environments are per-provider, not global —
avoiding the global-solver tar pit by design.

## 5. Namespaces & governance

- Plugin ids: reverse-DNS, first-publish-claims within a registry; disputes are
  registry policy (social layer, out of kernel scope).
- Capability namespaces (`cap:coords/…`): registry-governed ownership; publishing a
  capability doc into a namespace requires namespace membership. `core/` is reserved.
- Nothing prevents a lab from running a private registry with its own rules — the
  protocol is the only invariant.

## 6. Publication pipeline

```
submit archive → registry re-runs verification:
  manifest schema-valid · hashes match · signature valid (verified tier)
  · PluginContractTests pass in a clean sandbox
  · conformance cases pass for claimed capabilities
→ entry published with verification results attached (pass/fail is DISPLAYED,
  not hidden; failing conformance ⇒ cannot claim the capability)
→ yank supported (yanked versions resolvable only by exact pin, flagged)
```

Agent-generated plugins go through the identical pipeline with `generated-by` recorded
(AGENT_MODEL.md §6); the registry displays it.

## 7. Trust & mirroring

- Index signing: registry key signs `index.json`; clients pin keys on first add
  (TOFU + explicit fingerprint display) or via preconfigured key files.
- Mirrors serve the same signed tree; verification is end-to-end (hashes in the signed
  index), so mirrors need no trust.
- A compromised registry can serve a stale-but-valid index (freshness attack) — snapshot
  timestamps + max-age warnings mitigate; full TUF adoption is a roadmap item recorded
  as such (not claimed early).

## 8. Phasing (honesty rule)

- **Phase 5 artifact**: the index format spec + `RegistryClient` + file/HTTPS static
  implementations + local cache + `discover/show/fetch/verify` CLI — *no hosted
  service*. A git repo of index files is the first real registry.
- Hosted community registry (accounts, publishing service, web UI) is Phase 11 —
  ecosystem work, explicitly not a kernel dependency.

## 9. Testable contracts (Phase 5 gate)

- Round-trip: build index from a plugin corpus → refresh → search → fetch → verify →
  install, fully offline against `file://`.
- Tamper suite: modified archive, modified index entry, bad signature, yanked version ⇒
  correct refusal paths with clear errors.
- Precedence: id conflict across two registries resolves by priority, deterministically.
- Cache: search works with the network down; refresh failure degrades to cache with a
  staleness warning (RegistryError only when no cache exists).
- Capability search: seeded index answers "spectral analysis"-style queries via
  capability tags/synonyms, returning providers with comparison facts.
