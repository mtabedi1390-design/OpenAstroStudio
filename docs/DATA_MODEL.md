# Data Model

**Status:** Draft v0.1 · Companion to [ARCHITECTURE.md](ARCHITECTURE.md), [PROVENANCE.md](PROVENANCE.md)

A domain-neutral model for data flowing through the platform. The kernel understands
*structure, identity, and lineage* of data — never its scientific meaning. FITS,
spectra, molecules, meshes, genomes: all are plugin-defined schemas over the same
neutral primitives.

---

## 1. Nouns

```python
@dataclass(frozen=True)
class Artifact:
    """An immutable blob of bytes with identity = content."""
    id: str                     # "artifact:sha256/<hex>" — content-addressed
    media_type: str             # IANA type or "application/x.<vendor>"
    size: int
    schema: SchemaRef | None    # structural claim, validated when registered
    role: str                   # "output" | "log" | "figure" | "intermediate" | …
    storage: tuple[StorageRef, ...]  # where the bytes live (≥1)

@dataclass(frozen=True)
class Dataset:
    """A named, versioned, mutable-by-versioning collection of artifacts + metadata."""
    id: str                     # "dataset:<uuid>@<version>"
    name: str
    version: int                # new version = new immutable Dataset record
    parts: tuple[ArtifactRef, ...]
    schema: SchemaRef | None
    metadata: Mapping[str, Any] # schema'd, searchable (units, acquisition info, …)
    lineage: LineageRef         # how this version came to be (PROVENANCE.md)

@dataclass(frozen=True)
class SchemaRef:
    id: str                     # "schema:<namespace>/<name>@<major>"
    # resolves (via installed plugins / registry) to a JSON Schema document

@dataclass(frozen=True)
class Resource:
    """A reference to external data not managed by the platform."""
    id: str                     # "resource:<uuid>"
    uri: str                    # file://, https://, s3://, ssh://…, instrument://…
    access: AccessSpec          # credentials ref (never inline), permissions needed
    snapshot: SnapshotPolicy    # NONE | HASH_ON_READ | MATERIALIZE
```

`Transformation` and `Version` from the vision map to: every Dataset version's
`lineage` names the Execution that produced it — transformation *is* execution
(PROVENANCE.md §3); versions are immutable records, never in-place edits.

## 2. Schemas

- All structural claims use **JSON Schema** (draft 2020-12) — open standard, language-
  neutral, already the manifest/capability format.
- Schemas are namespaced/versioned like capabilities (`schema:coords/point-list@1`)
  and distributed by plugins or registries. The kernel ships only generic primitives:
  `schema:core/bytes@1`, `core/table@1` (columnar with typed columns),
  `core/tensor@1`, `core/tree@1` (JSON document), `core/text@1`.
- Domain schemas compose the primitives: a FITS-image schema is a plugin-provided
  schema over `core/bytes` + metadata contract, defined in an astronomy plugin — the
  kernel never learns what FITS is.
- Schema compatibility = same rules as capabilities (revisions additive, majors break).
  Port compatibility in workflows is checked structurally: producer schema must satisfy
  consumer schema (same id+major, or declared `compatible_with`).

## 3. Units

Domain-neutral treatment: quantities in metadata and tabular columns may carry a
`unit` string in **UCUM/VOUnits-compatible** syntax. The kernel: stores, compares for
*equality*, and refuses silently-unitless connections where a schema demands units.
The kernel does **not** convert units — conversion is scientific work: a `core/`
capability (`core/unit-conversion@1`) that providers (e.g. astropy.units, pint)
implement. This keeps unit knowledge out of the kernel while making conversion a
first-class, provenance-tracked operation.

## 4. Identity & integrity

- Artifacts are content-addressed (sha256). Same bytes ⇒ same artifact, automatic
  dedup, cheap integrity verification (`DataError` on hash mismatch at staging).
- Datasets/Resources get UUIDs; dataset versions are monotonically increasing ints.
- Storage is pluggable per `StorageRef` (local CAS `~/.smk/store/` in Phase 1; remote
  stores later behind the same `ArtifactStorage` protocol). Metadata lives in the
  StateStore; **payloads never enter SQLite**.

## 5. Projects and data

Project directories reference data, they don't embed it: `datasets/*.dataset.json`
records dataset ids + expected hashes. `scientific project verify` re-checks that all
referenced artifacts are present and hash-valid — a reproducibility primitive. Large
payloads stay in the CAS/remote stores; the project stays git-friendly.

## 6. Data movement between executions

- Inputs/outputs cross execution boundaries by **reference** (artifact hash / dataset
  id) with executor-mediated staging: the executor materializes referenced payloads
  into the workload's scratch dir (copy, hardlink, mount, or remote transfer — its
  choice, its descriptor declares the cost).
- Small literal values (parameters) pass by value in the Workload (JSON).
- Marshalling declared per invocation (`json` | `file` | `arrow` reserved for
  columnar zero-copy later). No pickling across boundaries, ever — pickles are
  neither language-neutral nor safe.

## 7. Domain neutrality test

The model must express, without kernel changes: an astronomy image (bytes + WCS
metadata schema), a chemistry trajectory (table/tensor), an engineering mesh (bytes +
mesh schema), a biology sequence set (table), an Earth-science raster stack (tensor +
geo metadata). Each needs only plugin-defined schemas. This is a standing review
criterion for any proposed kernel data-model change.

## 8. Testable contracts (Phases 1–2 gates)

- CAS: store/retrieve/dedup/corruption-detection round-trips.
- Schema registry: resolution, major/revision compatibility matrix, structural port
  compatibility checks (accept/reject table).
- Dataset versioning: immutability (new version ≠ mutation), lineage link required.
- Staging: reference inputs materialized correctly by `local-process`/`python-venv`;
  hash verified before run; `DataError` on mismatch.
- Neutrality: reference schemas for two unrelated domains (astronomy point-list +
  generic CSV table) round-trip through the same pipeline untouched by kernel code.
