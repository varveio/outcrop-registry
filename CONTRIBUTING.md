# Contributing

Outcrop Registry accepts focused corrections and new collections. Records are reviewed public
configuration, not raw analysis output — keep them factual and source-backed.

## Good contributions

- Correct a source publisher, homepage, license/attribution terms, or a broken source reference.
- Add a stable source reference for an existing claim.
- Improve a sourced summary while preserving (and citing) its references.
- Add a new collection that has clear source terms and public documentation.
- Flag a rights, attribution, or no-endorsement issue.
- Request removal or limited display if you are the publisher, steward, or an authorized
  representative for the source dataset.

## What we won't accept

- Raw object inventories or large object-key listings.
- Raw sample rows or source content dumps.
- Unverified license claims, or records that ignore unclear/missing/restrictive source terms.
- Copy that implies a source owner endorses Outcrop.
- AI-generated descriptions without source references.

## Record layout

A collection is a directory under `collections/<slug>/`:

- `collection.yaml` — collection-level record: `source` (publisher, homepage), `terms`
  (license/attribution), `summary`, the shared `refs[]` evidence pool, `tags`, and
  `display.canonical_path`.
- `<bucket>.yaml` — one file per bucket: its `bucket` name, `backend`, `role`, `region`, the engine
  `prefix`, and `prefixes[]` describing structurally significant paths (sourced copy, and
  `boundary: pin | exclude` only where the engine needs correcting).

Start from [`templates/collection.yaml`](templates/collection.yaml) and
[`templates/bucket.yaml`](templates/bucket.yaml). The full field reference is
[`docs/record-format.md`](docs/record-format.md); the evidence model is
[`docs/source-references.md`](docs/source-references.md).

## Source-reference rules

Every non-obvious claim must cite a reference from a `refs[]` pool:

- Use descriptive kebab-case ids (`aws-registry`, `terms-of-use`), not sequential numbers.
- Set `kind` to the material type (`registry_entry`, `catalog_metadata`, `publisher_doc`,
  `publisher_homepage`, `manifest`, …).
- Keep quoted `excerpt` values short (≤500 chars) and verbatim.
- Don't paraphrase a source description and present it as an original summary — cite it.
- If a claim was checked against its source, set `verification_status: verified_by_source`;
  otherwise leave it `unverified`. Don't mark anything `verified_by_review` unless a human reviewed it.

## Pull-request checklist

- [ ] `source.publisher` and `source.homepage_url` are present.
- [ ] `terms.license` and `terms.status` are set; if terms are unknown, the record says so.
- [ ] Required attribution and no-endorsement posture are preserved.
- [ ] Every non-obvious claim in `summary`, `facts[]`, and per-prefix `copy` cites a `refs[]` id.
- [ ] No raw content samples, sensitive object paths, or personal identifiers are included.
- [ ] No private model metadata (`model_id`, `prompt`, `confidence_score`) outside the sanctioned
      `stewardship.generated_by_model` disclosure block.
- [ ] `python3 scripts/validate_registry.py` passes without errors.
