# Record Format

> **Record format — directory layout.** Each collection is
> a directory `collections/<slug>/` containing two or more files:
> `collection.yaml` (identity, terms, refs, non-bucket locations, and
> collection-level facts) plus one `<bucket>.yaml` per storage bucket
> (backend, role, posture overrides, prefixes, and bucket-level facts).

Outcrop collection records live under `collections/`:

- A directory `collections/<slug>/` holding
  `collection.yaml` + one `<bucket>.yaml` per bucket.

Validated by `scripts/validate_registry.py` against
`schema/collection.schema.json` (collection file) and
`schema/bucket.schema.json` (bucket file).

A record is a reviewed, source-backed description of a public dataset:
where it lives, who publishes it, what the source terms are, and a
bounded set of editorial facts the Outcrop renderer turns into useful pages.
It is not engine output, not a model proposal, not an object inventory,
and not a mirror of an upstream catalog.

This document is the field reference for the record format. See also:
- [`registry-model.md`](registry-model.md) — the engine-leads model: the two resolution channels, `prefixes[]` shape, and wildcard precedence.
- [`annotations-guidance.md`](annotations-guidance.md) — guidance on using `facts[]`.
- [`source-references.md`](source-references.md) — the canonical taxonomy for `refs[]` and where each ref kind belongs.

## Directory layout

Every v0.4 collection is a directory:

```
collections/
  <slug>/
    collection.yaml       # identity, refs, terms, source, non-bucket locations
    <bucket>.yaml         # one file per bucket: backend, role, prefixes, facts
```

The bucket file's **filename stem must equal the `bucket` field** inside it
(`bucket: commoncrawl` → `commoncrawl.yaml`). The validator enforces this.

For collections with a single bucket (most), the layout is:

```
collections/commoncrawl/
  collection.yaml
  commoncrawl.yaml
```

For collections with multiple buckets, add one file per bucket:

```
collections/my-collection/
  collection.yaml
  my-primary-bucket.yaml
  my-archive-bucket.yaml
```

## Fact subject — positional scope

Fact **subject** is determined by where the fact is nested, not by any
`applies_to` or `level` field:

| Nesting location | Fact subject |
|---|---|
| `collection.yaml` top-level `facts[]` | The collection as a whole |
| `collection.yaml` `source.locations[].facts[]` | A specific collection-spanning non-bucket location |
| `<bucket>.yaml` top-level `facts[]` | The bucket |
| `<bucket>.yaml` `mirrors[].facts[]` | A specific mirror/replica of this bucket |
| `<bucket>.yaml` `prefixes[].facts[]` | A specific prefix within the bucket |

## Cross-file ref resolution

`refs[]` are defined in `collection.yaml`. Bucket files may define additional
refs local to that bucket. When a bucket file cites a ref id, the resolver looks
in the bucket file's own `refs[]` first, then falls back to `collection.yaml`'s
`refs[]` pool. Ref ids must be unique across all files in the collection directory.

## Posture rules (bucket overrides)

A bucket file may include `sensitivity_class`, `publication_scope`, `terms`, and
`sample_policy` to override the collection-level defaults for that bucket.
Overrides may only **tighten** (restrict) posture — a bucket file cannot loosen a
`sensitivity_class` or `publication_scope` set in `collection.yaml`.

## collection.yaml fields

`collection.yaml` holds identity, editorial content, refs, terms, and the
non-bucket parts of `source`. It does **not** contain `bucket`, `backend`,
`role`, `region`, `prefixes`, or any other bucket-specific fields.

| Field | Required | Values |
|---|---|---|
| `schema_version` | yes | `"0.4"` |
| `record_version` | yes | semver string, e.g. `"0.4.0"` |
| `slug` | yes | kebab-case, unique across the registry |
| `title` | yes | display title |
| `status` | yes | `draft | reviewed | published | withdrawn` |
| `sensitivity_class` | yes | `unrestricted | sensitive_pii_risk | restricted` — collection default |
| `publication_scope` | yes | `full | structure_only | minimal_listing | withheld` — collection default |
| `refs` | no | reference array — see [`§ refs[]`](#refs) |
| `terms` | yes | license and attribution — collection default; see [`§ terms`](#terms) |
| `sample_policy` | yes | what samples are permitted — collection default; see [`§ sample_policy`](#sample_policy) |
| `stewardship` | no | record-level default stewardship block |
| `summary` | no | collection-level editorial copy |
| `source_description` | no | publisher's own description (shown verbatim) |
| `source` | yes | source block (no bucket fields); see [`§ The source block`](#the-source-block) |
| `tags` | no | domain / format / pattern / access tags |
| `display` | no | display chrome (canonical_path, aliases, no_endorsement_text, report_issue_prefill) |
| `review_guidance` | no | preferred refs and reviewer notes |
| `facts` | no | collection-level facts; see [`§ facts[]`](#facts) |

## Bucket file (`<bucket>.yaml`) fields

Each bucket file describes one storage backend. The filename stem must equal the
`bucket` field. Bucket files inherit `terms`, `sample_policy`, `sensitivity_class`,
and `publication_scope` from `collection.yaml` unless they provide overrides (which
may only tighten posture).

| Field | Required | Values |
|---|---|---|
| `schema_version` | yes | `"0.4"` |
| `bucket` | yes | bucket name; **must equal filename stem** |
| `backend` | yes | `s3 | gcs | azure_blob` |
| `role` | yes | `primary | mirror | replica | archive | inventory | stac_catalog | metadata` |
| `title` | no | optional per-bucket display title — see [§ Per-bucket display title](#per-bucket-display-title) |
| `region` | no | cloud region string |
| `prefix` | no | optional root prefix within the bucket |
| `requester_pays` | no | boolean (default `false`; omit when false) |
| `account_required` | no | boolean (default `false`; omit when false) |
| `frozen` | no | boolean (default `false`; omit when false) |
| `superseded_by` | no | bucket name or non-bucket location id this bucket is superseded by |
| `terms` | no | posture override — may only tighten collection default |
| `sample_policy` | no | posture override — may only tighten collection default |
| `sensitivity_class` | no | posture override — may only tighten collection default |
| `publication_scope` | no | posture override — may only tighten collection default |
| `stewardship` | no | record-level default stewardship block for this bucket file |
| `refs` | no | refs local to this bucket file; ids must not duplicate `collection.yaml` refs |
| `facts` | no | bucket-level facts; see [`§ facts[]`](#facts) |
| `prefixes` | no | per-prefix annotations; see [`§ prefixes[]`](#prefixes) |

## Per-bucket display title

A bucket file may carry an optional top-level `title` field. When present, the
renderer uses it as the page title for that bucket's page instead of the
collection title from `collection.yaml`.

Use this when a secondary bucket holds a meaningfully distinct format or
audience from the collection as a whole — so readers land on a page whose
heading matches what they came to find:

```yaml
# openalex-mag-format.yaml
schema_version: '0.4'
bucket: openalex-mag-format
backend: s3
role: secondary
title: OpenAlex — MAG format
```

The primary bucket file and `collection.yaml` carry no `title`; they fall back
to the collection title. Only add `title` to a secondary bucket when the
bucket hosts a distinct enough artifact that its page would otherwise mislead
readers by showing the generic collection name.

**Naming guidance:** use the collection name as a prefix and append a concise
descriptor, separated by an em dash (—). Example: `OpenAlex — MAG format`.

## The `copy` shape (universal)

Every text-bearing field carries a `copy` block with up to four length tiers:

```yaml
copy:
  label: "Access"           # ~1–3 words; chip text, slot label
  headline: "Anonymous S3 requests fail — use signed AWS creds or the HTTP mirror"
  lede: "The s3://commoncrawl bucket is marked AccountRequired by AWS Open Data..."
  text: "Full body text..."  # the anchor; always required on facts/summary copy blocks
```

`text` is the anchor and fallback. `label`, `headline`, `lede` are optional — populate only those that carry **genuinely distinct** hand-authored content.

**`lede` authoring guidance:** author a `lede` only when it should differ from
`text` — typically a tighter ~30–40-word hero or card paragraph that introduces
the fact without repeating the full body. If `lede` would equal or render the
same as `text` under the fallback chain, omit it; the renderer falls back
`lede → text → headline`. The validator warns on a `lede` that is render-invariant.

**Discipline: copy tiers must carry only genuinely-distinct hand-authored content.** Never repeat a value across `label`/`headline`/`lede`/`text` tiers. If a shorter variant would render identically to what the fallback chain already resolves, omit it. `scripts/validate_registry.py` **warns** on any copy block where a shorter tier is render-invariant (redundant).

**Renderer fallback chains** (for a requested slot, first present field wins):

| Requested slot | Fallback chain |
|---|---|
| `label` | label → headline → text |
| `headline` | headline → lede → text |
| `lede` | lede → text → headline |
| `text` | text → lede |

**`locale`** defaults to `en`; omit it always.

Applied to: `summary.copy`, `source_description.copy`, every `facts[].copy` (collection-level, bucket-level, prefix-level, mirror-level), every `prefixes[].copy`, and every `source.locations[].copy`.

## The `stewardship` block

### Record-level default

A file may carry a top-level `stewardship` block that serves as the default for every annotation in that file. When a fact or prefix item omits its own `stewardship`, the record-level default applies:

```yaml
stewardship:                           # record-level default
  last_reviewed_at: "2026-05-19"
  last_reviewed_by: "system:v2-migration"
  generated_by: agent:web_research
  verification_status: unverified

facts:
  - id: my-fact
    copy: { text: "..." }
    refs: [my-ref]
    # stewardship absent → inherits record-level default
```

**Effective stewardship:** `item.stewardship ?? record.stewardship`.

### Per-annotation block

```yaml
stewardship:
  last_reviewed_at: "2026-05-19"
  last_reviewed_by: "user@example"
  generated_by: human                  # see enum below
  verification_status: unverified      # see enum below
  generated_by_model:                  # OPTIONAL — AI Act Article 50
    provider: anthropic
    model_id: claude-opus-4-7
    generated_at: "2026-05-19T14:32:00Z"
  stale_after: "2026-11-15"            # OPTIONAL
```

`generated_by` values:

| Value | Meaning |
|---|---|
| `human` | Hand-authored by a contributor |
| `agent:web_research` | Produced by an AI agent doing web research |
| `agent:bucket_listing` | Produced by an AI agent enumerating bucket structure |
| `source:registry_yaml` | Lifted directly from a registry YAML |
| `source:publisher_doc` | Lifted directly from a publisher's documentation |
| `source:catalog_metadata` | Lifted directly from a machine-readable catalog |

`verification_status` values:

| Value | Meaning |
|---|---|
| `unverified` | Not yet reviewed by a human |
| `verified_by_review` | Human reviewed and approved |
| `verified_by_source` | Verified by fetching and checking the cited source |
| `verified_by_engine` | Verified by reconciling against engine output |

## `refs[]`

Reference array — all evidence for facts in the file. In `collection.yaml`, the pool is shared across the collection; bucket files may add their own local refs. Annotations cite by id. See [`source-references.md`](source-references.md) for the complete reference model.

```yaml
refs:
  - id: aws-registry
    kind: registry_entry
    url: https://github.com/awslabs/open-data-registry/blob/main/datasets/example.yaml
    label: "AWS Open Data Registry YAML for example"
    excerpt: "Name: Example. ARN: arn:aws:s3:::example. Region: us-east-1."
    retrieved_at: "2026-05-15"
```

## The `source` block

`source` in `collection.yaml` describes who publishes the collection, what optional
non-bucket locations exist, and how the collection is registered. It does not
contain bucket fields (`bucket`, `backend`, etc.) — those live in the bucket file.

```yaml
source:
  publisher: "Common Crawl Foundation"    # (required) attribution name
  homepage_url: https://commoncrawl.org/  # (required) publishing org's homepage
  dataset_page_url: https://commoncrawl.org/get-started  # optional

  maintainers:
    - name: "Amazon Web Services"
      role: host                          # host | redistributor | curator
      url: https://aws.amazon.com/opendata/

  identifiers:
    doi: 10.xxxx/xxxx
    ror: 02k1qz970

  locations: ...    # NON-BUCKET locations only (HTTP, FTP, etc.) — see § Non-bucket locations
  registry_entries: ...
  sponsorships: ...
```

### Mirrors — bucket-scoped access paths (`mirrors[]` in bucket files)

A mirror, replica, or alternate representation of a **specific bucket's content**
(HTTP mirror, FTP, BigQuery, differently-named replica bucket) goes in that
**bucket file's `mirrors:`** list, NOT in `collection.yaml source.locations[]`.

**Placement rule:**
- Access path serves **this bucket's content** → `<bucket>.yaml mirrors[]`
- Access path spans **multiple buckets** or is a publisher portal/DOI not tied to one bucket → `collection.yaml source.locations[]`

```yaml
# In commoncrawl.yaml (bucket file):
mirrors:
  - id: http-mirror
    backend: http
    role: mirror
    base_url: https://data.commoncrawl.org/
    anonymous: true

# In gdelt-open-data.yaml (bucket file):
mirrors:
  - id: gdelt-http-live
    backend: http
    role: primary
    base_url: http://data.gdeltproject.org/
    anonymous: true
    facts:
      - id: live-data-http
        intent: start_here
        topic: access
        scope: inherited
        copy:
          text: "For live GDELT data, fetch http://data.gdeltproject.org/gdeltv2/lastupdate.txt..."
        refs: [gdelt-data-page, gdelt-v2-lastupdate]

  - id: gdelt-bigquery
    backend: other
    role: replica
```

Mirror facts nest on the mirror entry (subject is the mirror). The mirror id
(`gdelt-http-live`) enters the collection's id namespace alongside bucket names
and `collection.yaml source.locations[]` ids — it can be cited in `superseded_by`
and `sponsorships.covers`.

Mirror fields: `id` (required), `backend` (required), `role` (required), `base_url`
(required for http/ftp), `repo` (huggingface), `record_id` (zenodo), `bucket`,
`region`, `anonymous`, `frozen`, `superseded_by`, `terms`, `sensitivity_class`,
`publication_scope`, `sample_policy`, `facts[]`.

### Non-bucket locations (`collection.yaml source.locations[]`)

`source.locations[]` carries only access paths that span the collection as a whole
or are not tied to a single bucket — publisher portals, DOIs, registry entries
serving multiple buckets, etc. For single-bucket collections, `source.locations[]`
is typically empty; all mirrors live in the bucket file.

Each non-bucket location may carry a `facts[]` array for facts whose subject is that location:

```yaml
source:
  locations:
    - id: publisher-portal
      backend: http
      role: primary
      base_url: https://example.org/data/
      facts:
        - id: portal-note
          intent: operational_note
          topic: access
          copy:
            text: "The publisher portal indexes all buckets; use it for discovery."
          refs: [publisher-doc]
```

### `source.registry_entries[]`

```yaml
registry_entries:
  - registry: aws_open_data    # aws_open_data | gcp_public_datasets | azure_open_datasets | huggingface | data_gov | stac_catalog | planetary_computer | zenodo | other
    ref: aws-registry          # id from refs[]
```

### `source.sponsorships[]`

The `covers` list uses **bucket filename stems**, **bucket-file mirror ids**, or
**collection-level location ids**.

```yaml
sponsorships:
  - program: aws_open_data
    sponsor: AWS
    covers: [commoncrawl]      # bucket filename stem
```

## `terms`

```yaml
terms:
  license: Apache-2.0          # SPDX expression or sentinel — primary license identity
  status: linked               # verified | linked | unknown | excluded
  name: "Apache 2.0"
  url: https://...
  license_spdx_id: Apache-2.0  # deprecated alias for license; kept for compatibility
  required_attribution: "Publisher Name"
  no_endorsement_required: true
  display_policy: structure_only  # include | structure_only | exclude
  reviewed_at: null
  notes: "..."
```

**`license`** is the primary license identity, expressed as an SPDX expression
(`MIT`, `CC-BY-4.0`, `ODbL-1.0`, etc.) or one of the SPDX sentinels:

- `NOASSERTION` — the precise dataset-level license has not been confirmed from
  sources (terms are bespoke, mixed, or the publisher has not issued an explicit
  license statement). Use this when `status` is `unknown` or `linked` and no
  SPDX id can be verified. Do not remove the `notes` field — the prose note is
  still a useful editorial fact alongside the sentinel.
- `NONE` — no license applies (e.g. dedicated to the public domain without a
  formal license instrument).

`status`, `display_policy`, and the other editorial fields are Outcrop metadata
alongside `license`, not replacements for it. `license_spdx_id` is a deprecated
alias — use `license` for new records.

`display_policy: include` requires `status: verified`. Drafts with unreviewed terms should use `structure_only`.

**On CC-BY-* and ODbL-* records**, `display.no_endorsement_text` is **REQUIRED**.

## `sample_policy`

```yaml
sample_policy:
  raw_object_samples: disallow_by_default
  path_templates: allow
  schema_samples: allow_if_non_sensitive
  notes: "..."
```

## `summary` and `source_description`

Optional collection-level editorial copy in `collection.yaml`:

```yaml
summary:
  copy:
    headline: "..."
    lede: "..."
    text: "..."
  refs: [...]
  stewardship: { ... }

source_description:
  copy:
    text: "..."
  refs: [...]
  stewardship: { ... }
```

`source_description` is shown to readers verbatim, attributed to the source.

## `display`

```yaml
display:
  canonical_path: /1000-genomes/
  aliases:
    - /1000genomes/
  no_endorsement_text: "Outcrop is not affiliated with or endorsed by ..."
  report_issue_prefill:
    collection: 1000-genomes
    refs: [aws-registry]
```

## `facts[]`

Source-backed editorial annotations rendered into specific page surfaces. Subject
is determined positionally (see [§ Fact subject — positional scope](#fact-subject--positional-scope) above).

```yaml
facts:
  - id: start-here              # kebab-case; unique within collection directory
    intent: start_here          # see enum below
    topic: access               # see enum below
    severity: caution           # OPTIONAL; for intent: warning
    scope: inherited            # OPTIONAL; see § scope below
    copy:
      label: "Start here"
      headline: "Use the data.commoncrawl.org HTTP mirror for browsing..."
      lede: "Start at data.commoncrawl.org..."
      text: "Full body text..."
    refs: [data-index, aws-registry]
    coverage: full              # full | manifest | sampled | partial (omit when full)
    confidence: high            # high | medium | low (omit when high)
    relationship:               # OPTIONAL — present only on intent: relationship
      type: index_for
      target: "https://index.commoncrawl.org/collinfo.json"
      direction: outbound
    also: [other-fact-id]       # OPTIONAL — related facts
    note: "..."                 # OPTIONAL — non-rendered maintainer note
    stewardship: { ... }
```

`text` is required in `copy`.

**`also[]` vs `relationship`** — these are not interchangeable:

- `also: [other-fact-id]` is **intra-record renderer fan-out**: it attaches the
  same fact to additional prefix surfaces within the same collection directory,
  as if the fact were authored at each listed id. It is a display convenience,
  not a semantic edge.
- A `relationship` block (on `intent: relationship` facts) is a **semantic
  edge** to another dataset or URL outside this fact's immediate subject — a
  `mirror_of`, `derived_from`, `index_for`, etc. relationship.

Use `also` when you want one fact to appear in multiple related prefix pages.
Use `relationship` when you want to express "this dataset is semantically
connected to that URI".

### `intent` enum

| `intent` | When |
|---|---|
| `warning` | Flag something that affects access, license, quality, freshness. Set `severity`. |
| `correction` | Refute a misconception |
| `start_here` | Orient a first-time user |
| `relationship` | Describe how this dataset relates to another. Populate the structured `relationship` block. |
| `description` | Describe a structural or format property without alarm |
| `operational_note` | Practical access/tooling guidance |

### `topic` enum

| `topic` | Subject |
|---|---|
| `access` | Credentials, mirrors, regions, requester-pays, account requirements |
| `legal_terms` | License, attribution, redistribution restrictions |
| `format` | File formats, encoding, content layout inside files |
| `structure` | Path layout, partition shape, prefix organization |
| `catalog` | Machine-readable catalogs (STAC, Iceberg, manifest.json) |
| `lineage` | Provenance, sibling/replacement relationships |
| `quality` | Data caveats |
| `freshness` | Update cadence, staleness |
| `contributors` | Multi-party publishing |

### `severity` enum

`info | caution | warning`. Default `caution` on `intent: warning` annotations.

### `scope` (optional)

Controls how the annotation propagates to descendant surfaces. Defaults are applied by the renderer based on `(intent, topic)`; explicit `scope:` overrides the default.

| `scope` | Behavior |
|---|---|
| `exact` | Renders only at the page whose subject matches this fact's location |
| `inherited` | Renders at the subject AND propagates as a chip on descendant pages |
| `related` | Renders at the subject AND as a chip on sibling / cross-referenced pages |

Renderer default `scope` per `(intent, topic)` combination:

| `(intent, topic)` pair | Default |
|---|---|
| `(start_here, *)` | `inherited` |
| `(warning, *)` | `inherited` |
| `(description, structure)` | `exact` |
| `(description, format)` | `exact` |
| `(description, freshness)` | `exact` |
| `(correction, *)` | `exact` |
| `(relationship, *)` | `related` |
| `(operational_note, *)` | `inherited` |
| **fall-through** | `exact` |

### Structured `relationship` block

```yaml
relationship:
  type: index_for               # mirror_of | derived_from | index_for | metadata_for | hosted_by | supersedes | superseded_by | related_to
  target: "..."                 # absolute URI or collection:<slug>
  direction: outbound           # outbound | inbound
```

`target` must be an absolute URI (containing `://`). When using `collection:<slug>` form, the slug MUST resolve in the registry.

### Facts placement — three-level subject hierarchy

Facts are placed at one of three levels across the collection directory:

- **`collection.yaml` top-level `facts[]`** — facts about the collection as a whole (applies to all buckets).
- **`collection.yaml` `source.locations[].facts[]`** — facts about a specific non-bucket location.
- **`<bucket>.yaml` top-level `facts[]`** — facts about that specific bucket.
- **`<bucket>.yaml` `prefixes[].facts[]`** — facts about a specific prefix within the bucket.

```yaml
# collection.yaml
facts:
  - id: multi-bucket-note
    intent: description
    topic: structure
    copy:
      text: "This collection spans two buckets."
    refs: [aws-registry]

source:
  locations:
    - id: http-mirror
      backend: http
      role: mirror
      base_url: https://example.org/
      facts:
        - id: http-mirror-anon
          intent: start_here
          topic: access
          copy:
            text: "The HTTP mirror serves anonymous access."
          refs: [data-page]

# my-bucket.yaml
facts:
  - id: bucket-frozen
    intent: warning
    topic: freshness
    scope: inherited
    copy:
      text: "The S3 bucket is a frozen snapshot; live data is on the HTTP mirror."
    refs: [aws-registry]

prefixes:
  - prefix: events/
    kind: named_dataset
    copy:
      text: "GDELT 1.0 event records from 1979."
    refs: [data-page]
    facts:
      - id: format-csv-events
        intent: description
        topic: format
        copy:
          text: "Files under events/ are tab-delimited despite the .csv extension."
        refs: [data-page]
```

## `prefixes[]`

A flat list of per-prefix annotations in the bucket file. Each item keys to a relative
prefix path within the bucket.

**One principle drives this section:** the prefix path is **relative** to the bucket — no `s3://bucket/` prefix. Paths must end with a trailing slash. Wildcards: `*` (one segment), `**` (zero or more), `{a,b,c}` (alternation), `key=*` (Hive partition).

```yaml
prefixes:
  - prefix: events/              # relative path; trailing slash required
    kind: named_dataset          # OPTIONAL enum; see below
    copy:
      label: "GDELT 1.0 Event Database"
      headline: "Event records from 1979, one file per day"
      text: "Full body text."
    refs: [data-page, codebook]
    tags: [historical]           # OPTIONAL remaining tags after kind is extracted
    inherit: false               # OPTIONAL; default false
    expected_count:              # OPTIONAL — see § expected_count and drift
      value: 123
      counted_at: "2026-05-15"
      source_ref: collinfo
    drift:                       # OPTIONAL — see § expected_count and drift
      warn_above_pct: 10
    terms:                       # OPTIONAL — per-prefix terms override
      status: unknown
      ...
    boundary: exclude            # OPTIONAL — pin | exclude
    featured: true               # OPTIONAL — pin to the top of the Featured cards
    note: "..."                  # OPTIONAL — non-rendered maintainer note
    declared_by: publisher_doc   # OPTIONAL
    coverage: sampled            # OPTIONAL (omit when full)
    confidence: medium           # OPTIONAL (omit when high)
    stewardship: { ... }         # OPTIONAL
    facts: [ ... ]               # OPTIONAL — nested facts[] for this prefix
    id: my-prefix-id             # OPTIONAL — stable handle
```

### `kind` field

An optional enum giving the dataset type of this prefix:

`crawl | release | chain | table | named_dataset | partitioned_table | stac_collection | other`

Use it for the primary type of the prefix; any remaining editorial tags go in `tags[]`.

### `boundary` field

Structural instruction consumed at ingestion:

| Value | Meaning |
|---|---|
| `pin` | Force a boundary at this prefix (the engine missed it) |
| `exclude` | Suppress a boundary at this prefix (the engine wrongly emitted it) |

Absent means trust the engine. When `boundary` is present, `refs[]` is required: a
publisher document for a *semantic* correction, or a `measured_structure` ref (the
bucket's own re-derivable structure) for a *structural* one — see
[`source-references.md`](source-references.md) and `registry-model.md § Structural-instruction
channel`. A plain-language `note` justifying the correction should accompany it.

**Container-fact vs boundary — dividing line:**

The statement "this prefix is a container, not a dataset" can be expressed two
ways, and contributors should choose based on whether the engine is wrong:

- Use `boundary: exclude` when the engine **emitted a spurious dataset boundary**
  at this prefix and the correction must take effect at ingestion. This is a
  structural instruction: the engine got it wrong, and the registry corrects it.
  Example: the engine treats `v1.1/stellar/parquet/{pubnet,testnet}/v1/` as a
  dataset root; `boundary: exclude` suppresses it.
- Use a `description/structure` fact (in `facts[]`) when the engine is **correct
  to not emit a boundary** but you want to communicate to readers that the prefix
  is a container rather than a direct-access dataset. This is editorial context,
  not a structural correction.

Never use `boundary: exclude` to annotate a prefix the engine already handles
correctly just to add editorial flavor. If the engine produced no boundary at a
container prefix and you only want to explain its role, a `facts[]` entry is the
right channel.

### `featured` field

An optional editorial pin. `featured: true` promotes this prefix to the top of the
**Featured** cards on its parent page (the small set of "start here" datasets shown
above the structure table).

Featured is normally chosen automatically — Outcrop ranks a bucket's datasets by a
blend of size and recency and shows a handful, one per dataset *family* (so a bucket
of monthly snapshots shows the latest, not ten near-identical cards). Use `featured`
only to override that automatic choice for a dataset you want to guarantee a top slot.

Rules and behavior:

- **Datasets only.** `featured` takes effect only on a prefix the engine discovered
  as a dataset (a boundary). It reorders existing datasets; it cannot create a card
  for a folder/container or for a prefix the engine never emitted. A `featured` pin
  on a non-dataset prefix is silently inert.
- **One card per family.** If the pinned prefix is a wildcard (e.g.
  `crawl-data/CC-MAIN-*/`), the single best-scoring matching dataset is featured — a
  wildcard pin means "always feature the best/most-recent member of this family,"
  not "feature every match." This keeps the Featured row varied.
- **Per-entry; not inherited.** Like `boundary` and `note`, `featured` applies only
  to the entry that declares it and never cascades to descendants (it is unaffected
  by `inherit`).
- No `refs[]` are required — `featured` is an editorial preference, not a structural
  correction.

```yaml
# Always feature the most recent main crawl, whichever it currently is:
- prefix: crawl-data/CC-MAIN-*/
  featured: true
```

### `expected_count` and `drift`

Registry → engine reconciliation contract.

```yaml
prefixes:
  - prefix: crawl-data/CC-MAIN-*/
    kind: crawl
    expected_count:
      value: 123
      counted_at: "2026-05-15"
      source_ref: collinfo       # id from refs[]
    drift:
      warn_above_pct: 10         # warn if observed differs by >10%
```

`drift` shape:

| Key | Meaning |
|---|---|
| `warn_above_pct: N` | Warn if observed count differs from `expected_count.value` by >N% |

### `inherit` field

When `true`, this prefix item's enrichment cascades to descendant engine prefixes as a per-field fallback. See [`registry-model.md § Enrichment inheritance`](registry-model.md#enrichment-inheritance).

### `extent` field (reserved)

`extent` is reserved for engine-derived spatial and temporal coverage metadata. Contributors should leave it empty — the engine populates it where possible from object metadata and manifest analysis.

### Prefix-addressable backends only

`prefixes[]` items resolve against the bucket's engine-ingested prefix tree. Only `s3://`, `gs://`, and `azure://` backend buckets are supported. For other backends, describe the collection via `facts[]` and `summary`.

### Cardinality guidance

There is no hard cap on `prefixes[]`. The editorial posture is: enumerate collection-shaping prefixes only — chain containers, named dataset roots, release families. The validator warns above 150 items.

## `record_version` semantics

`record_version` is a semver string (`"major.minor.patch"`). The `major.minor` tracks the schema generation (`"0.4"`). The `patch` segment increments on content revisions to a published record — e.g. `"0.4.1"` is the first content revision after the initial `"0.4.0"`. Leave `patch` at `0` when first authoring a record.

`record_version` is a field on `collection.yaml` only; bucket files do not carry it.

## Validator rules

Beyond field-level schema validation, the validator enforces:

- **`collection.yaml` required** — every `collections/<slug>/` directory must contain `collection.yaml`.
- **At least one bucket file required** — every collection directory must have at least one `<bucket>.yaml`.
- **`bucket` equals filename stem** — the `bucket` field in a bucket file must equal the YAML file's filename stem.
- **`schema_version: "0.4"` on bucket files** — required.
- **`slug` uniqueness** — `collection.yaml` slug must be globally unique across all collection directories.
- **`prefixes[].refs` resolution** — every cited id must resolve in the collection-level ref pool (bucket file's own `refs[]` first, then `collection.yaml`'s).
- **`prefixes[].prefix` grammar** — must be relative (no leading `s3://` or `/`), end with `/`, no empty path, valid segments.
- **`boundary` without refs** (ERROR) — `boundary: pin/exclude` with no `refs[]` citation.
- **`facts[].refs` resolution** — every cited id must resolve in the applicable ref pool.
- **Fact id uniqueness** — all fact ids across all files in a collection directory must be unique.
- **Ref id uniqueness** — ref ids must not be duplicated across `collection.yaml` and bucket files in the same directory.
- **`superseded_by` resolution** — must name a bucket filename stem or non-bucket location id in the same collection.
- **`sponsorships.covers` resolution** — ids must resolve to bucket filename stems or non-bucket location ids.
- **Posture only-tightens** — bucket file `sensitivity_class` / `publication_scope` may not loosen collection defaults.
- **`terms.display_policy: include`** requires `terms.status: verified` (SOFT warning when record is `draft`).
- **CC-BY / ODbL → no_endorsement_text required**.
- **Duplicate ref ids** (WARNING) — warns when two refs share the same id across files in the directory.
- **Correction-prose heuristic** (WARNING) — `prefixes[].copy` text matching `Corrected YYYY-MM-DD` pattern belongs in `note:` instead.
- **Per-excerpt cap** — `refs[].excerpt` ≤ 500 chars.
- **Per-source aggregate cap** — sum of excerpt lengths per host ≤ 1500 chars (warns at 80%).

Schema enforcement uses `additionalProperties: false` throughout — unknown fields are rejected.

## Naming rules

- **Field names and enum values:** `snake_case`
- **`id` values:** `kebab-case`, unique within the collection directory. No underscores. Child ids use `<parent-id>.<child-name>` (dot separator).
- **Booleans:** positive phrasing — `boundary`, `requester_pays`, `account_required`, `frozen`, `anonymous`.
- **Quoted dates:** always quote date strings in YAML — `retrieved_at: "2026-05-10"`.

## What does not belong

- `model_id`, `model_provider`, `prompt`, `confidence_score` at the record root or inside annotations (private model metadata). The exception is `stewardship.generated_by_model.{provider, model_id, generated_at}`.
- `refs[].kind: varve_inference` or `refs[].kind: bucket_listing` — private; engine output only, never authored.
- Raw object inventories or full path lists.
- Unreviewed automated descriptions.
- Raw paths on `sensitive_pii_risk` records (template patterns only).
- `prefixes[].boundary: pin/exclude` without a source-backed `refs` entry.
- `bucket`, `backend`, `role`, `region`, or `prefixes` in `collection.yaml`.
