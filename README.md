# Outcrop Registry

The public, contributable source records behind **[Outcrop](https://outcrop.varve.io)** — a
field guide to open datasets in object storage.

Outcrop runs a discovery engine over public object-storage buckets (starting with open buckets
on Amazon S3) and publishes what it finds: dataset boundaries, path templates, formats, storage
cost, freshness, and a sourced summary of each dataset. This repository holds the **human-readable,
source-backed configuration** that grounds that work — one record per collection — not the engine's
computed output.

Outcrop is built and operated by **[Varve](https://varve.io)**, the commercial system of record
for private object storage. The same engine that powers Outcrop runs on private buckets in the
Varve product. Outcrop is not affiliated with or endorsed by AWS, any cloud provider, or any
dataset publisher unless explicitly stated.

## What's in here (and what isn't)

**In:** for each collection, a directory of YAML records describing its public datasets — the
source publisher and homepage, license and attribution terms, stable source references, structural
hints for the engine (which prefixes are real dataset boundaries), and sourced editorial summaries.

**Not in:** the engine's computed analysis (discovered boundaries, path templates, cost, recency).
That lives on the [Outcrop website](https://outcrop.varve.io), produced by running the engine over
each bucket's object inventory.

### AI-assisted content, openly reviewable

Editorial summaries are drafted with AI assistance and grounded in cited sources (the AWS Open Data
Registry entry, the publisher's own documentation, and other public material). Every non-obvious
claim carries a source reference. Because AI-assisted text can be wrong, the records live here in
public so anyone can inspect them and open a pull request — the same model as the registries Outcrop
draws from. Fields marked `verification_status: verified_by_source` were checked against the cited
source; `unverified` means not yet reviewed.

## Repository layout

```text
collections/
  <slug>/
    collection.yaml         # collection-level record (publisher, terms, summary, refs)
    <bucket>.yaml           # one file per bucket in the collection (structure, prefixes)
docs/                       # the record format and authoring guidance
schema/
  collection.schema.json    # JSON Schema for collection.yaml
  bucket.schema.json        # JSON Schema for <bucket>.yaml
templates/                  # blank starting points for a new collection
scripts/validate_registry.py
```

A **collection** is a registry-entry-level grouping (e.g. Common Crawl, Sentinel-2) with one or
more **buckets**. Each bucket file describes that bucket's structure: the prefixes that are real
dataset boundaries, and sourced notes about what lives where.

## The record format

Records use the current format (`schema_version: "0.4"`). The authoritative references are:

- [`docs/record-format.md`](docs/record-format.md) — the full field reference and layout.
- [`docs/registry-model.md`](docs/registry-model.md) — the model: what the registry asserts vs.
  what the engine computes, and how the two reconcile.
- [`docs/source-references.md`](docs/source-references.md) — the evidence/reference model.
- [`docs/annotations-guidance.md`](docs/annotations-guidance.md) — authoring `facts[]` and per-prefix copy.

Start from [`templates/collection.yaml`](templates/collection.yaml) and
[`templates/bucket.yaml`](templates/bucket.yaml), and validate against the JSON Schemas in
[`schema/`](schema/).

## Contributing

Corrections and new collections are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for what makes
a good contribution and the pull-request checklist. Before opening a PR, run the validator:

```bash
pip install -r requirements.txt
python3 scripts/validate_registry.py
```

CI runs the same check on every pull request.

## Contact

Open an [issue](../../issues) for corrections, new collections, or publisher requests. If you're a
publisher or steward and would rather not file a public issue, email **outcrop@varve.io** directly.

## License

Varve-authored registry content is licensed **CC BY 4.0** (see [`LICENSE`](LICENSE)).
Source-derived material — publisher names, source paths, quoted excerpts, upstream license and
attribution text — remains under its original upstream terms; see [`NOTICE.md`](NOTICE.md) for the
boundary. Attribution should identify "Outcrop Registry" and link to the relevant Outcrop page or
this repository.
