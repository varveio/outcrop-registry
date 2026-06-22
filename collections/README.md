# Collection Records

Each subdirectory describes one Outcrop collection:

```text
<slug>/
  collection.yaml     # collection-level record (publisher, terms, summary, refs)
  <bucket>.yaml       # one file per bucket (structure, prefixes)
```

Records are intentionally compact. They are reviewed public configuration, not raw analysis output.

Start from [`../templates/collection.yaml`](../templates/collection.yaml) and
[`../templates/bucket.yaml`](../templates/bucket.yaml), and use the records here for concrete shape.
The full field reference is [`../docs/record-format.md`](../docs/record-format.md).

Each record should carry:

- Source publisher and homepage (`source`).
- License and attribution terms (`terms`), including the no-endorsement posture.
- Source references in a `refs[]` pool with semantic kebab-case ids (e.g. `aws-registry`,
  `terms-of-use`), cited by every non-obvious claim.
- A sample policy for whether raw object examples may be shown.
- Sourced editorial summaries — grounded in the cited refs, not raw model output.
