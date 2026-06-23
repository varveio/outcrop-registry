# Outcrop Registry Model — Engine-Leads, Registry-Enriches

This document explains the record model: the engine-leads principle, the two
resolution channels, the `prefixes[]` shape, wildcard precedence, and opt-in
inheritance. Read this before authoring a record.

---

## The principle

The Outcrop discovery engine determines which storage prefixes exist, which are
boundaries (dataset roots), and how they are classified. The registry's job is:

- **Enrichment** — attaching labels, descriptions, citations, and editorial tags to
  engine-known prefixes, for display and search.
- **Corrections** — a narrow set of genuine cases where the engine got a boundary
  wrong, applied server-side at ingestion.

The registry never *declares* structure at render time. Enrichment is resolved at
display time; corrections are applied at ingestion so the engine/API output already
carries them. The UI always sees engine output, not a registry-shaped view.

"Engine-leads" does not mean "the engine is always right." When the engine
misclassifies a boundary, the registry corrects it — but the correction flows into
the engine's data at ingestion, not into the UI at render.

---

## The two resolution channels

### 1. Enrichment channel — display time, may fan out

When rendering a concrete engine prefix `P` within a bucket, find every `prefixes[]`
item whose `prefix` matches `P` (using relative paths — `P` with the bucket stripped).
Apply the most-specific match's enrichment (`copy`, `refs`, `tags`, `kind`). A single
pattern item `crawl-data/CC-MAIN-*/` enriches all matching release prefixes and
auto-covers new ones the moment the engine ingests them.

Enrichment only adds labels and text. It never changes structure.

### 2. Structural-instruction channel — ingestion time only

A prefix item's `boundary` field is consumed at ingestion: expand `prefix` over the
engine tree and pin or exclude each matching prefix.

- `boundary: pin` — force a boundary the engine missed.
- `boundary: exclude` — suppress a spurious boundary.

Structural instructions are rare. Most collections have none. Each instance must
cite a `refs` entry justifying the override, and should carry a plain-language
`note` explaining the reasoning (e.g. *"the sub-directories below this are internal
partitions of one dataset, released together"*) — both so a reviewer can judge the
correction and so a contributor proposing their own pin has a model to follow.

Two kinds of justification, by what the correction asserts:

- **Semantic** — "these are (or aren't) distinct datasets by meaning." Cite a
  publisher document or catalog (`publisher_doc`, `publisher_file`,
  `catalog_metadata`, `manifest`).
- **Structural** — "the engine split one dataset into many (or vice versa) by
  shape." Common when sub-paths are opaque per-record identifiers (UUIDs, hashes)
  or partition keys (`date=…/`, `state=…/`). These have no publisher document; the
  evidence is the bucket's own measured structure, cited as a `measured_structure`
  ref (a re-derivable listing of the bucket — anyone can confirm it by listing the
  objects). A `measured_structure` ref may back a `boundary` correction but nothing
  else (it can never justify a license, access, or other terms claim).

### 3. Presentation channel — render time only

A prefix item's `featured: true` is a presentation preference, not structure. Like
enrichment it never changes what the engine discovered; it only promotes a dataset to
the top of the **Featured** cards on its parent page. It takes effect only on a prefix
the engine discovered as a dataset (a boundary), and a wildcard pin features the single
best-scoring matching dataset (one card per family). No `refs` required — it asserts a
preference, not a fact. See [`record-format.md`](record-format.md) § `featured` field.

---

## The `prefixes[]` shape

A collection is a directory with a `collection.yaml` and one bucket file per
bucket. Per-prefix annotations live in a flat `prefixes[]` list in the bucket file.
Each item keys to a **relative** prefix path within that bucket:

`collections/my-collection/collection.yaml`:
```yaml
schema_version: "0.4"
record_version: "0.4.0"
slug: my-collection
title: "My Collection"
status: reviewed
sensitivity_class: unrestricted
publication_scope: full

refs:
  - id: data-page
    kind: publisher_doc
    url: https://example.org/data
    label: "Publisher data page"

terms:
  status: linked
  ...

sample_policy:
  raw_object_samples: disallow_by_default
  path_templates: allow
  schema_samples: allow_if_non_sensitive

source:
  publisher: "Example Publisher"
  homepage_url: https://example.org/
```

`collections/my-collection/my-bucket.yaml`:
```yaml
schema_version: "0.4"
bucket: my-bucket
backend: s3
role: primary

prefixes:
  - prefix: events/              # relative path; no s3://bucket/ prefix
    kind: named_dataset          # optional kind enum
    copy:
      label: "Events"
      headline: "Event records from 1979, one file per day"
      text: "Full body text."
    refs: [data-page, codebook]
    boundary: pin                # OPTIONAL structural correction (rare)

  - prefix: releases/*/          # pattern — enriches all matching prefixes
    kind: release
    copy:
      headline: "Versioned release (Parquet)"
      text: "Each release-YYYY-MM-DD/ is one quarterly snapshot..."
    refs: [release-manifest]
    inherit: false               # opt-in cascade — see below
```

### Field reference

| Field | Channel | Required | Meaning |
|---|---|---|---|
| `prefix` | both | **yes** | Relative prefix path (`events/`) or pattern (`releases/*/`, `{a,b,c}/`, `key=*/`). No leading `s3://bucket/` or `/`. Trailing `/` required. |
| `kind` | enrichment | no | Optional dataset type enum: `crawl \| release \| chain \| table \| named_dataset \| partitioned_table \| stac_collection \| other`. Omit on leaf tables — engine classifies them; author `kind` only on containers. |
| `copy` | enrichment | no | The copy block — `{ label?, headline?, lede?, text? }`. At least one tier must be present. |
| `refs` | enrichment | no | Citation ids into `refs[]`. |
| `tags` | enrichment | no | Additional editorial tags. `tags` union across all matching prefix items. |
| `inherit` | enrichment | no (default `false`) | When `true`, enrichment cascades to descendant engine prefixes as a per-field fallback. |
| `boundary` | structure | no (absent = trust the engine) | `pin` = force a missed boundary; `exclude` = suppress a spurious boundary. Consumed at ingestion only. Never inherited. Requires `refs` (kind in `publisher_file`/`catalog_metadata`/`publisher_doc`/`manifest` for a *semantic* boundary, or `measured_structure` for a *structural* one — see below). Should carry a plain-language `note` justifying the correction. |
| `expected_count` | structure | no | Count expectation for catalog-anchored prefixes — see `record-format.md § expected_count and drift`. |
| `drift` | structure | no | Drift policy for `expected_count` — `warn_above_pct`, `warn_above`, or `error_if_missing`. |
| `id` | — | no | OPTIONAL stable handle, unique within the file: kebab-case. |
| `note` | — | no | OPTIONAL non-rendered maintainer note. **Never rendered**; reader-facing copy belongs in `copy`. |
| `declared_by` | enrichment | no | Provenance: `publisher_catalog \| external_catalog \| publisher_doc`. Inherits per precedence order (see [§ Per-field resolution](#per-field-resolution)). |
| `coverage` | enrichment | no (default `full`) | `full \| manifest \| sampled \| partial`. **Omit when `full`.** Inherits per precedence order. |
| `confidence` | enrichment | no (default `high`) | `high \| medium \| low`. **Omit when `high`.** Inherits per precedence order. |
| `terms` | — | no | Per-prefix terms override. Full replacement — not a merge. Inherits whole block per precedence order. |
| `extent` | enrichment | no | Geographic and temporal extent: `{ bbox?: [w,s,e,n] \| [[...]], temporal?: [start\|null, end\|null] }`. See [§ `extent`](#extent). |
| `stewardship` | — | no | Optional provenance tracking block. Inherits from record-level default when absent. |
| `facts` | — | no | Facts whose subject is this prefix — see `record-format.md § facts[]`. |

### Record-level stewardship default

A record may carry a top-level `stewardship` block that serves as the default for every annotation.

### Mirrors and non-bucket locations

**Placement rule:** an access path that serves **this bucket's content** (HTTP mirror, FTP, BigQuery representation, replica bucket) goes in the bucket file's `mirrors[]` list. An access path that spans **multiple buckets** or is not tied to one bucket (publisher portal, DOI) stays in `collection.yaml source.locations[]`.

The mirror id enters the collection's id namespace alongside bucket filename stems and `collection.yaml source.locations[]` ids. It may be cited in `superseded_by` (e.g. a frozen archive bucket superseded by an HTTP live mirror) and `sponsorships.covers`.

---

## Wildcard precedence and field-wise resolution

When rendering a prefix `P`, enrichment is resolved by building an ordered
**contributor list** and then resolving **per field** over that list.

### Contributor list

1. All **direct matches** — prefix items whose `prefix` matches `P` (concretely
   or via pattern). Ordered by specificity:
   1. A **concrete-prefix** item (no wildcards) beats any pattern item.
   2. Among patterns, **fewer wildcards** wins; tie → **longer literal prefix**.
   3. Still tied → **more literal path segments**.
   4. Still tied → **longest literal string**.
   5. Still tied → **lexicographic order** of `prefix` (deterministic backstop).
2. Then all **inherit ancestors** — `inherit: true` items whose `prefix` is a
   strict ancestor of `P` — ordered by the same specificity rules (nearer
   ancestor first). Direct matches always precede ancestors.

### Per-field resolution

Over the ordered contributor list:

- **`copy`** (description) — **local: resolved from DIRECT matches only** (the
  prefix item's own entry, plus any pattern entries whose `prefix` matches `P`),
  **never from `inherit: true` tree ancestors.** A per-tier merge across those
  direct contributors (`label`/`headline`/`lede`/`text`, each from the first
  direct contributor that carries it). This keeps a container's blurb from
  bleeding onto its descendants — e.g. an `eth/blocks/` table never renders as
  the chain's "Ethereum mainnet" headline; a prefix with no direct entry has no
  copy and the renderer falls back to the engine-derived name. (Subtree-metadata
  below DOES cascade — that's the dedup mechanism; only `copy` is local.)
- **`tags`** — union across **all** contributors (direct + ancestors).
- **`refs`** — the refs list of the **first** contributor whose `refs` is non-empty
  (direct → nearest inherit ancestor → …).
- **`kind`** — the **first** contributor that carries a `kind` value.
- **`terms`** (whole block, no inner field merge) — first value found in: direct
  prefix item → nearest `inherit: true` ancestor → bucket-file `terms` default
  → collection `terms`. The whole block is taken from the winning contributor;
  fields inside are never merged across contributors.
- **`declared_by`**, **`coverage`**, **`confidence`** — scalar, resolved in the
  same order: direct → nearest inherit ancestor → bucket-file default →
  collection default.
- **NEVER inherited (strictly per-entry): `boundary`, `note`, `id`.** These
  fields are per-item facts and are never resolved from ancestors or defaults.

There is no numeric `priority` field. The rule-based order is deterministic.

### Bucket-file defaults

A bucket file may carry top-level `declared_by`, `terms`, `coverage`, and
`confidence` fields that serve as the lowest-priority defaults for every prefix
in that file, below `inherit: true` ancestor resolution. These fields are
inherited by prefix items when no more-specific contributor supplies a value.

Render-invariance rule: the registry strips a child field only when its value is
identical to the value that the resolver would supply via this precedence order.
Under-stripping is always safe; over-stripping would silently change rendered
output.

### Worked micro-example

Container item `v1.0/btc/` with `inherit: true`:
```yaml
- prefix: v1.0/btc/
  kind: chain
  copy:
    label: "Bitcoin mainnet"
    headline: "Bitcoin mainnet — blocks and transactions tables."
    text: "Bitcoin mainnet in Parquet, partitioned by date..."
  refs: [bucket-manifest]
  inherit: true
```

Child item `v1.0/btc/blocks/` (label-only):
```yaml
- prefix: v1.0/btc/blocks/
  kind: table
  copy:
    label: "blocks"
  refs: [bucket-manifest]
```

Resolved for `v1.0/btc/blocks/`:
- `label` → `"blocks"` (from child)
- `headline` → `"Bitcoin mainnet — blocks and transactions tables."` (from container via inherit)
- `text` → `"Bitcoin mainnet in Parquet, partitioned by date..."` (from container via inherit)
- `refs` → `[bucket-manifest]` (child refs used)
- `tags` → union of both (none in this example)
- `kind` → `table` (from child — child's kind takes precedence)

---

## Enrichment inheritance — opt-in

By default, a prefix item's enrichment attaches only where its `prefix` directly
matches a concrete engine prefix. It does **not** cascade down the prefix tree.

Set `inherit: true` on an item to make it a **fallback contributor** for
descendant engine prefixes. With field-wise resolution, a child prefix that has
its own label-only item still picks up the container's headline, body, and refs
as per-field fallbacks.

Use `inherit: true` only where the enrichment is genuinely true of the whole
subtree. A release-level blurb should not bleed onto every file partition within
it — leave `inherit` at `false` in those cases.

`inherit` governs enrichment only. `boundary` is never inherited.

---

## `kind` as a first-class optional field

The editorial dataset-type enum (`crawl | release | chain | table | named_dataset |
partitioned_table | stac_collection | other`) is an optional field on prefix items:

```yaml
prefixes:
  - prefix: crawl-data/CC-MAIN-*/
    kind: crawl
    copy:
      headline: "Monthly main crawl..."
      text: "..."
```

`kind` carries no structural authority. The engine's own classifiers are the source
of truth; `kind` is editorial colour for display, browse facets, and filtering.

Any additional editorial tags go in `tags[]`.

---

## Facts placement

One principle drives facts placement: **annotations live where their subject lives**.

| Subject | Where facts go |
|---|---|
| The bucket or collection as a whole | Top-level `facts[]` |
| A specific prefix | `prefixes[<item>].facts[]` |
| A non-bucket location (HTTP mirror, FTP) | `source.locations[<item>].facts[]` |

---

## Prefix-addressable backends only

`prefixes[]` items resolve against the hoisted bucket's engine-ingested prefix
tree. The engine maintains prefix trees for S3 (`s3://`), GCS (`gs://`), and
Azure Blob (`azure://`). For other backends — HTTP, FTP, HuggingFace, Zenodo,
IPFS, Globus — the engine does not maintain a prefix tree. Describe such
locations via `source.locations[].facts[]` and `summary`.

---

## Edge cases

| Case | Handling |
|---|---|
| One description → many prefixes (e.g. `CC-MAIN-*/`) | Enrichment channel, display-time fan-out. One pattern prefix item. |
| A specific note over a family default | Most-specific precedence: the concrete/closer item wins. |
| A pattern carries both enrichment and `boundary` | One item: enrichment at display + structural instruction at ingestion. The two channels coexist. |
| New concrete prefixes appear after authoring | Pattern auto-covers enrichment; ingestion re-applies `boundary` on re-ingest. |
| `prefix` has no matching engine prefix | A data review issue — never rendered; not a structural row. |

---

## `extent`

The optional `extent` field carries geographic and temporal extent information
for a collection or prefix. It is intended for enrichment the engine cannot
derive automatically — the engine derives statistics from data; `extent` is
editorial context about the real-world coverage of a dataset.

```yaml
extent:
  bbox: [-180, -90, 180, 90]    # [west, south, east, north] in WGS-84 decimal degrees
  temporal: ["2008-01-01", "2015-12-31"]  # [start|null, end|null] RFC 3339 dates/datetimes
```

`bbox` may be a single bounding box `[w, s, e, n]` or an array of bounding
boxes `[[w1, s1, e1, n1], [w2, s2, e2, n2], ...]` when the dataset spans
non-contiguous regions.

`temporal` is a two-element array `[start, end]`; either element may be `null`
for open-ended ranges. Values are RFC 3339 date strings or datetime strings.

No CRS field or geometry field is included — extents in this schema are always
WGS-84 bounding boxes.

`extent` at the collection top-level covers the collection as a whole.
`extent` on a prefix item covers that prefix's content.

---

## Stub-elimination rule

A prefix entry carries value when it adds information the engine cannot derive:
a real description, a citation, a boundary correction, distinct terms, an
expected_count, or a non-table kind.

**A prefix item that reduces to `{kind: table, copy: {label: <last-path-segment>}}`
MUST be omitted.** Such items are bare stubs: the engine classifies leaf tables
independently, and the label equals the path segment the renderer would already
show. Keeping them inflates the record without adding useful information.

Delete stub items when:
- `kind` is `table` (or absent, and the engine classifies the prefix as a table)
- `copy` contains only a `label` whose value equals the last path segment
- No `refs`, `boundary`, `terms`, `expected_count`, `declared_by`, `facts`, or
  any other enrichment field is present

Keep items that carry any enrichment the engine cannot supply. Chain/named
dataset/release/partitioned_table containers always carry enrichment and must
be kept.

The validator warns on a bare table stub.

---

## Related docs

- [`record-format.md`](record-format.md) — full field reference for the record format.
- [`annotations-guidance.md`](annotations-guidance.md) — guidance on `facts[]`.
- [`source-references.md`](source-references.md) — the canonical taxonomy for `refs[]`.
