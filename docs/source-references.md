# Source References

Every claim in a registry record is source-backed. Sources live in
the top-level `refs[]` array and are cited by id from `prefixes[]`,
`facts[]`, `summary`, `source_description`, and `source.locations[].facts[]`.

This document covers the reference shape, the canonical `kind`
taxonomy, when to use each kind, and the citation discipline.

For the broader record format see [`record-format.md`](record-format.md);
for annotation guidance see [`annotations-guidance.md`](annotations-guidance.md).

## Reference shape

```yaml
refs:
  - id: aws-registry                                # kebab-case; unique within the file
    kind: registry_entry
    url: https://github.com/awslabs/open-data-registry/blob/main/datasets/example.yaml
    label: "AWS Open Data Registry YAML for example"
    excerpt: "Name: Example. ARN: arn:aws:s3:::example. Region: us-east-1."  # ≤500 chars; OPTIONAL
    retrieved_at: "2026-05-15"                      # quoted ISO date; OPTIONAL
```

Required fields: `id`, `kind`, `url`, `label`. `excerpt` and `retrieved_at` are
recommended for the load-bearing refs (the ones backing non-obvious claims).

`id` is the citation handle other parts of the record use:

```yaml
facts:
  - id: account-required
    intent: warning
    topic: access
    refs: [aws-registry]    # ← cites this ref by id
    ...
```

The same ref can back multiple facts. Reuse ids; don't duplicate refs.

## The canonical `kind` taxonomy

| `kind` | Meaning | Use for |
|---|---|---|
| `publisher_homepage` | The publisher's main homepage | The "home" link to the publishing org |
| `publisher_doc` | A publisher's documentation, README, or technical page | Most editorial claims about the dataset (what it is, how it's organized, how to use it) |
| `publisher_file` | A file shipped by the publisher in or alongside the bucket — README in the bucket root, in-bucket index, paths.gz, manifest fragments | In-bucket evidence |
| `catalog_metadata` | A machine-readable catalog — STAC, Iceberg, DCAT, project-specific JSON catalogs (collinfo.json, graphinfo.json) | Catalog-backed claims (counts, listings, item-level descriptions) |
| `file_metadata` | Metadata read from inside a file — Parquet footer, NetCDF/HDF5/Zarr header | Schema / encoding claims (rare; usually engine-side) |
| `registry_entry` | A public dataset registry's listing for this collection — AWS Open Data Registry YAML, GCP Public Datasets, HuggingFace Hub model card, Zenodo record | Cross-registry identity |
| `web_research` | A third-party web source — academic papers, project portals not at the publisher, FAQs, wikis, vendor blogs | Background context not in publisher's own docs |
| `measured_structure` | A snapshot of the bucket's own object/prefix structure (counts, prefixes) — re-derivable by listing the bucket | **Structural `boundary` corrections only** — justifying a `pin`/`exclude` when sub-paths are opaque ids or partition keys the engine mis-split. Never justifies a license/access/terms claim. |

Two more values exist in the canonical taxonomy but **must never appear in
`refs[].kind`** (they're reserved for engine output):

- `varve_inference` — discovery-engine inference output; never authored by hand. The
  validator **rejects** any record whose `refs[]` uses this kind.
- `bucket_listing` — an agent's own ad-hoc enumeration of bucket structure done while
  researching (engine pre-output, not authoritative). Not a citable reference.

Note the distinction from `measured_structure` above: `measured_structure` is the
*canonical, re-derivable* snapshot of the bucket's object/prefix structure and **is** a
valid `refs[].kind` — but only to back a `boundary` correction (never a terms claim).
`bucket_listing` is an informal working enumeration and is never cited.

## When to use each kind

### `publisher_doc` (most common)

The publisher's own documentation — project websites, READMEs on the project's
domain, `docs.example.org`, "Get Started" pages.

```yaml
- id: cc-get-started
  kind: publisher_doc
  url: https://commoncrawl.org/get-started
  label: "Common Crawl: Get Started"
  retrieved_at: "2026-05-15"
```

### `publisher_file`

Documents placed *in or beside the bucket* — discoverable by listing the bucket.
A README at the bucket root, an `index.html` listing, a `paths.gz`, a `manifest.json`.

```yaml
- id: sample-crawl-page
  kind: publisher_file
  url: https://data.commoncrawl.org/crawl-data/CC-MAIN-2026-17/index.html
  label: "CC-MAIN-2026-17 file listings page"
  excerpt: "The April 2026 crawl archive contains 2.19 billion pages..."
  retrieved_at: "2026-05-15"
```

### `catalog_metadata`

Machine-readable catalogs and table-format metadata.

```yaml
- id: collinfo
  kind: catalog_metadata
  url: https://index.commoncrawl.org/collinfo.json
  label: "Common Crawl crawl catalog (collinfo.json)"
  excerpt: '{"id": "CC-MAIN-2026-17", "name": "April 2026 Index", ...}'
  retrieved_at: "2026-05-15"
```

### `registry_entry`

A public registry's listing for this collection.

```yaml
- id: aws-registry
  kind: registry_entry
  url: https://github.com/awslabs/open-data-registry/blob/main/datasets/commoncrawl.yaml
  label: "AWS Open Data Registry YAML for commoncrawl"
  excerpt: "Name: Common Crawl. ARN: arn:aws:s3:::commoncrawl. Region: us-east-1."
  retrieved_at: "2026-05-15"
```

For AWS Open Data Registry, the `url` MUST point at the GitHub YAML source
(`github.com/awslabs/open-data-registry/blob/main/datasets/<slug>.yaml`),
not the rendered page. The validator warns if it doesn't.

### `publisher_homepage`

The publisher's main org homepage.

```yaml
- id: cc-homepage
  kind: publisher_homepage
  url: https://commoncrawl.org/
  label: "Common Crawl homepage"
```

### `web_research`

Third-party sources outside the publisher's own materials.

```yaml
- id: depcc-paper
  kind: web_research
  url: https://arxiv.org/abs/1710.01779
  label: "DepCC: A Dependency-Parsed Web-Scale Corpus (LREC 2018)"
  excerpt: "DepCC is the largest-to-date linguistically analyzed corpus in English..."
  retrieved_at: "2026-05-19"
```

## Semantic ids

Ref ids are **kebab-case** semantic handles unique within the file:

- `aws-registry` — the AWS Open Data Registry entry
- `cc-homepage` — the Common Crawl homepage
- `collinfo` — the CC catalog file
- `cc-terms` — the publisher's terms-of-use page

Avoid: numeric ids (`ref-1`), opaque hashes, agent-internal codes.

## Citation discipline

Every non-obvious claim cites at least one ref:

- **Editorial copy** (`summary`, `source_description`) — cites the refs that support the prose.
- **`facts[]`** — `refs[]` is **required** with ≥1 entry.
- **`prefixes[]`** — `refs[]` recommended for all items with non-trivial claims.
- **`boundary: pin/exclude`** — `refs[]` is **required** with ≥1 entry.

If a claim has no source, it doesn't belong in the registry.

## Excerpts

`excerpt` carries a short, verbatim, attributed snippet from the cited source.

**Discipline:**

- Short — **≤500 chars per excerpt** (validator-enforced).
- Verbatim — quote the source's actual words. Don't paraphrase.
- Attributed — the ref's `label` + `url` provide the attribution.
- Aggregate cap — the sum of excerpt lengths across all refs sharing a single
  host MUST be **≤1500 chars per record** (validator-enforced at 80% of either
  limit as a warning).

## License identity and source references

The `terms.license` field in a record holds the primary SPDX expression (e.g.
`MIT`, `CC-BY-4.0`) or sentinel (`NOASSERTION` / `NONE`) for the dataset's
terms. Sources cited in the `terms.url` and `refs[]` pool back this field: when
a source does not assert a recognized SPDX license, set `license: NOASSERTION`
and keep the prose note in `terms.notes`. The `status` and `display_policy`
fields are Outcrop editorial metadata alongside `license`; they do not replace
it.

## Rights model

Source-derived material in `excerpt` fields **remains under the original source's
license / terms**. The registry's CC-BY-4.0 license covers Outcrop's *structured
metadata* (field shapes, editorial selection, Outcrop-authored descriptions) —
**not** the quoted excerpts.

Downstream consumers redistributing the registry should:

- Preserve `excerpt` text verbatim with its attached attribution
- Respect each cited source's own license / terms
- Honor takedown or correction requests routed through this repo's issue templates

For more on the registry's two-layer licensing posture, see [NOTICE.md](../NOTICE.md).

## Forbidden in `kind`

- `varve_inference` — engine output, never authored
- `bucket_listing` — engine pre-output, never authored

The validator rejects records that use these values for `refs[].kind`.
