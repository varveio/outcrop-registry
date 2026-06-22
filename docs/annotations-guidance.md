# Annotations Guidance

This is a contributor reference for the annotation sections in a record:
`facts[]` (primary, nested at subject) and `prefixes[]` (per-prefix enrichment).

For the full field reference, see [`record-format.md`](record-format.md).
For the source-references model (used by every annotation's `refs[]`), see
[`source-references.md`](source-references.md).

## When to add each section

| Section | Add when… |
|---|---|
| `prefixes[]` | There are per-prefix labels, descriptions, citations, editorial kind, or structural instructions to attach to specific storage prefixes. |
| `facts[]` (top-level) | There are source-backed editorial sentences about the bucket or collection as a whole — access warnings, start-here guidance, freshness warnings, relationships. |
| `prefixes[].facts[]` | There are source-backed editorial sentences specific to a particular prefix — format notes, corrections, relationships to sibling paths. |
| `source.locations[].facts[]` | There are source-backed editorial sentences about a specific non-bucket location (e.g. "use this HTTP mirror for anonymous access"). |

All sections require source backing (`refs[]`). None of them should carry
engine output, counts, sizes, or raw model proposals.

## Cardinality caps (guardrails, not targets)

| Section | Cap | Notes |
|---|---|---|
| `prefixes[]` | No hard cap; validator warns above 150 | Enumerate collection-shaping prefixes only. Use one pattern item for large families. |
| `facts[]` (all levels combined) | 30 | Collection-wide budget across all surfaces. Not per-page. |

Add a fact only when it is genuinely useful to a reader, not to fill the budget.

---

## `prefixes[]`

### When to add a prefix item

Write one item per prefix with **distinct identity** — its own name, description,
or citation that differs from its siblings. Do not enumerate every date partition,
file, or Hive partition value.

**Stub-elimination rule:** Do NOT author a prefix item that reduces to a bare
`{kind: table, copy: {label: <last-path-segment>}}`. The engine classifies leaf
tables independently and the renderer already shows the path segment as the name.
A stub like this adds no information and inflates the record. Author a prefix item
only when it carries something the engine cannot derive: a real description, a
citation, a boundary correction, distinct terms, an expected_count, or a
non-table kind. See [`registry-model.md § Stub-elimination rule`](registry-model.md#stub-elimination-rule).

### prefixes[] vs facts[]

Both can key to the same prefix. The split is explicit:

- **`prefixes[]` = the prefix's primary identity** — "what is this?": its label,
  card headline, editorial lede, kind, citations, and editorial tags. One conceptual
  item per meaningful prefix.
- **`prefixes[].facts[]` = typed, scoped annotations** — "what do I watch out for /
  where do I start / how does this relate to X?": access warnings, freshness
  warnings, format corrections, relationships. They carry `intent` / `topic` /
  `severity` and their own `scope` propagation.

### Cardinality guidance

Enumerate collection-shaping prefixes only — chain containers, named dataset
roots, release families. For a large family of identically-structured prefixes,
write one pattern item (e.g. `crawl-data/CC-MAIN-*/`). For large catalogs, use
`expected_count` and `drift`. The validator warns above 150 items.

### Optional `id` and `note` fields

- `id` — a stable handle, unique within the file: kebab-case. Add when a prefix
  item needs to be tracked across renames; omit for simple label-only items.
- `note` — a non-rendered maintainer note: audit trail, justification prose,
  dated correction history. Never rendered on any page. Reader-facing copy
  belongs in `copy`.

### Field-wise enrichment resolution

When more than one prefix item contributes to a prefix (direct matches + `inherit: true`
ancestors), enrichment resolves per field: `tags` union across all contributors;
`refs` from the first contributor with a non-empty refs list; each `copy` tier
independently from the first contributor that carries it. See
[`registry-model.md § Wildcard precedence and field-wise resolution`](registry-model.md#wildcard-precedence-and-field-wise-resolution)
for the full specification.

---

## `facts[]`

Source-backed editorial annotations the Outcrop renderer routes into specific
page slots. Facts are nested at their subject. Each fact has up to six
axes of metadata plus a body (`copy`):

```yaml
facts:
  - id: account-required           # kebab-case; unique within file
    intent: warning                # what kind of annotation is this?
    topic: access                  # what is it about?
    severity: caution              # how strongly does it warn? (for intent: warning)
    scope: inherited               # OPTIONAL; how should it propagate?
    copy:
      label: "Account required"
      headline: "S3 primary rejects anonymous requests"
      lede: "The s3://commoncrawl bucket is marked AccountRequired by AWS Open Data..."
      text: "Full body; always populated."
    refs: [aws-registry]
    coverage: full                 # full | manifest | sampled | partial (omit when full)
    confidence: high               # high | medium | low (omit when high)
    also: [related-fact-id]        # OPTIONAL — related facts for renderer cross-linking
    note: "..."                    # OPTIONAL — non-rendered maintainer note
    stewardship: { ... }
```

`text` is always required in `copy`. `scope` defaults are applied by the renderer
based on `(intent, topic)`; omit it when the default is correct.

**Omit-defaults discipline:** `coverage: full` and `confidence: high` are defaults — omit them.

**Stewardship inheritance:** when absent, the record-level top-level `stewardship`
block applies as the default.

### The two key axes: `intent` and `topic`

`intent` says **what kind of annotation it is**:

| `intent` | When to use |
|---|---|
| `warning` | The user could be misled or harmed by missing this fact. Always set `severity`. |
| `correction` | A common misconception worth refuting. *"The columnar index is Parquet, not Iceberg."* |
| `start_here` | First-time-user orientation. |
| `relationship` | This collection's relationship to another dataset. Populate the structured `relationship` block. |
| `description` | A structural or format fact without alarm. |
| `operational_note` | Practical access / tooling guidance. |

`topic` says **what the annotation is about**:

| `topic` | About |
|---|---|
| `access` | Credentials, regions, mirrors, requester-pays, account requirements |
| `legal_terms` | License, attribution, redistribution restrictions |
| `format` | File formats, encoding, content layout |
| `structure` | Path layout, partition shape, prefix organization |
| `catalog` | Machine-readable catalogs (STAC, Iceberg, manifest.json) |
| `lineage` | Provenance, sibling/replacement relationships |
| `quality` | Data caveats |
| `freshness` | Update cadence, staleness |
| `contributors` | Multi-party publishing |

### `severity` (for warning intent)

`info | caution | warning`. Default `caution`. Use `info` for soft advisories;
`warning` for the strongest emphasis.

### `scope` — how the annotation propagates

| `scope` | Behavior |
|---|---|
| `exact` | Renders only at the page whose subject matches this fact's location |
| `inherited` | Renders at the subject AND propagates as a chip on descendant pages |
| `related` | Renders at the subject AND as a chip on sibling / cross-referenced pages |
| `hidden_below` | Renders only at the subject; explicitly NOT inherited |

Renderer default `scope` per `(intent, topic)` pair:

| `(intent, topic)` | Default |
|---|---|
| `(start_here, *)` | `inherited` |
| `(warning, *)` | `inherited` |
| `(description, structure)` | `exact` |
| `(description, format)` | `exact` |
| `(correction, *)` | `exact` |
| `(relationship, *)` | `related` |
| `(operational_note, *)` | `inherited` |
| **fall-through** | `exact` |

### Relationship-intent annotations: the structured edge

```yaml
- id: crawl-catalog
  intent: relationship
  topic: catalog
  copy:
    text: "The publisher's collinfo.json enumerates every monthly main crawl..."
  refs: [collinfo, graphinfo]
  relationship:
    type: index_for
    target: "https://index.commoncrawl.org/collinfo.json"
    direction: outbound
```

`type` values: `mirror_of | derived_from | index_for | metadata_for | hosted_by | supersedes | superseded_by | related_to`

**`target` semantics:**
- For "this collection has a catalog file X" → `target` is the catalog file URL.
- For "this dataset is a sibling/distinct from Y" → `target` is the sibling path.
- For "this is hosted by X" → `target` is the host's URL.
- For "this collection supersedes / is superseded by another Outcrop collection"
  → `target` is `collection:<slug>` and the slug MUST resolve in this registry.

### Choosing `(intent, topic)` — examples

| Fact | Choice |
|---|---|
| *"The bucket is marked AccountRequired; anonymous requests fail."* | `intent: warning, topic: access, severity: caution` |
| *"Custom Terms of Use, no SPDX license."* | `intent: warning, topic: legal_terms, severity: caution` |
| *"The columnar index is Apache Parquet, not Iceberg or Delta."* | `intent: correction, topic: format` |
| *"This `v1.0/` prefix groups multiple datasets by schema version."* | `intent: correction, topic: structure` |
| *"Start at data.commoncrawl.org; S3 requires AWS credentials."* | `intent: start_here, topic: access` |
| *"Each monthly crawl has ~100 segments with parallel WARC/WAT/WET shards."* | `intent: description, topic: format` |
| *"Top-level layout: crawl-data/, cc-index/, projects/, contrib/."* | `intent: description, topic: structure` |
| *"AWS hosts the primary copy under its Open Data Sponsorship Program."* | `intent: relationship, topic: contributors` + `relationship.type: hosted_by` |
| *"Datasets under contrib/ carry their own licenses, not the parent ToU."* | `intent: operational_note, topic: legal_terms` |

### Volume framing

A typical record carries ~10 facts distributed across ~5 surfaces (collection
page + bucket page + N prefix pages). The cap of 30 is a **collection-wide**
budget. Most records use 6–12 facts.

---

## Per-annotation `stewardship`

Every `facts[]` item and every prefix item may carry a `stewardship` block.
See [`record-format.md § The stewardship block`](record-format.md#the-stewardship-block).
The minimum on every annotation:

```yaml
stewardship:
  last_reviewed_at: "2026-05-19"
  last_reviewed_by: "<github-handle-or-email>"
  generated_by: human              # or agent:web_research / source:publisher_doc / etc.
  verification_status: unverified
```

On forward edits where you're using an AI tool to author, also include:

```yaml
  generated_by_model:
    provider: anthropic
    model_id: claude-opus-4-7
    generated_at: "2026-05-19T14:32:00Z"
```

The `generated_by_model` sub-block satisfies EU AI Act Article 50 attribution
on AI-authored content.
