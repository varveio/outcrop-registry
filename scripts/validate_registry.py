#!/usr/bin/env python3
"""Validate Outcrop Registry collection records."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]

RESERVED_SLUGS = {
    "format", "explore", "about", "api", "auth", "admin",
    "settings", "docs", "status", "new",
}

# Fields that must never appear in a public record
DISALLOWED_FIELD_NAMES = {
    "model_id", "model_provider", "prompt", "confidence_score",
    "extracted_at", "varve_refs", "varve_summary",
    "varve_materials", "outcrop_summary", "v1_display_policy",
    "enrichment_hints", "review_notes",
}

# ref kinds that can back a boundary correction. Publisher-grade documents justify a
# *semantic* boundary call; ``measured_structure`` — a snapshot of the bucket's own
# object/prefix structure (re-derivable by listing the bucket) — justifies a
# *structural* one (e.g. opaque per-record sub-paths or partition keys the engine
# over-split). A structural over-/under-split has no publisher document; its evidence
# is the measured structure itself.
BOUNDARY_VALID_REF_KINDS = {
    "measured_structure", "publisher_file", "catalog_metadata", "publisher_doc", "manifest",
}

# Valid enum values for prefix item fields
PREFIX_DECLARED_BY_VALUES = {"publisher_catalog", "external_catalog", "publisher_doc"}
PREFIX_COVERAGE_VALUES = {"full", "manifest", "sampled", "partial"}
PREFIX_CONFIDENCE_VALUES = {"high", "medium", "low"}
PREFIX_KIND_VALUES = {
    "crawl", "release", "chain", "table", "named_dataset",
    "partitioned_table", "stac_collection", "other",
}
PREFIX_BOUNDARY_VALUES = {"pin", "exclude"}

# Posture orderings for only-tighten check
SENSITIVITY_ORDER = {"unrestricted": 0, "sensitive_pii_risk": 1, "restricted": 2}
PUBLICATION_ORDER = {"full": 0, "structure_only": 1, "minimal_listing": 2, "withheld": 3}

# AWS Open Data GitHub URL prefix
AWS_ODR_GITHUB_PREFIX = "https://github.com/awslabs/open-data-registry/"

# Accession-shaped patterns
ACCESSION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'SRR\d{6,}'),
    re.compile(r'HG\d{5}'),
    re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I),
]

# URI pattern grammar constants
_LITERAL_SEG_RE = re.compile(r'^[a-zA-Z0-9._=:\-]+$')
_HIVE_SEG_RE = re.compile(r'^[a-zA-Z0-9._\-]+=\*$')
_BRACE_SEG_RE = re.compile(r'^\{([^{}/]+)\}$')

_CORRECTION_DATE_RE = re.compile(r'\bCorrected \d{4}-\d{2}-\d{2}\b')


# ---------------------------------------------------------------------------
# URI / prefix grammar helpers
# ---------------------------------------------------------------------------

def _validate_uri_segment(seg: str) -> str | None:
    """Validate one path segment (no '/').  Returns error string or None."""
    if seg in ('**', '*'):
        return None
    if _HIVE_SEG_RE.match(seg):
        return None
    if seg.startswith('{'):
        m = _BRACE_SEG_RE.match(seg)
        if not m:
            return f"malformed brace expression {seg!r}: must be {{alt1,alt2,...}} with no slashes or nested braces"
        parts = m.group(1).split(',')
        if len(parts) < 2:
            return f"brace expression {seg!r} has fewer than 2 alternatives"
        for p in parts:
            if not p:
                return f"brace expression {seg!r} has an empty alternative"
            if not _LITERAL_SEG_RE.match(p):
                return f"brace alternative {p!r} contains disallowed characters"
        return None
    if seg.endswith('*'):
        prefix = seg[:-1]
        if '*' in prefix or '{' in prefix or '}' in prefix:
            return f"segment {seg!r}: wildcards only allowed as trailing * in a literal prefix"
        if prefix and not _LITERAL_SEG_RE.match(prefix):
            return f"segment {seg!r}: literal prefix contains disallowed characters"
        return None
    if _LITERAL_SEG_RE.match(seg):
        return None
    return f"segment {seg!r}: contains disallowed characters (allowed: a-zA-Z0-9._=:-)"


def validate_relative_prefix(prefix: str, context: str) -> str | None:
    """
    Validate a v0.4 relative prefix value.
    Rules: no leading slash; must end with '/'; not empty string or '/';
    each segment must be valid per the wildcard grammar.
    Returns an error message or None.
    """
    if not prefix:
        return f"{context}: prefix must not be empty string; use the bucket-level facts[] instead"
    if prefix == '/':
        return f"{context}: prefix '/' is not valid; use the bucket-level facts[] instead"
    if prefix.startswith('/'):
        return f"{context}: prefix {prefix!r} must not start with '/'; relative paths only (e.g. 'events/')"
    if not prefix.endswith('/'):
        return f"{context}: prefix {prefix!r} must end with '/'"
    # Strip trailing slash and validate each segment
    inner = prefix[:-1]
    segs = inner.split('/')
    for seg in segs:
        if not seg:
            return f"{context}: prefix {prefix!r} contains an empty path segment"
        err = _validate_uri_segment(seg)
        if err:
            return f"{context}: prefix {prefix!r}: {err}"
    return None


def validate_uri_pattern(applies_to: str) -> str | None:
    """Validate a full URI pattern (for relationship.target, also: values)."""
    scheme_end = applies_to.find('://')
    if scheme_end == -1:
        return f"URI pattern {applies_to!r}: missing ://"
    scheme = applies_to[:scheme_end]
    if scheme not in ('s3', 'gs', 'https', 'http', 'hf', 'azure', 'zenodo', 'ftp'):
        return f"URI pattern {applies_to!r}: unknown scheme {scheme!r}"
    rest = applies_to[scheme_end + 3:]
    has_trailing_slash = rest.endswith('/')
    if has_trailing_slash:
        rest = rest[:-1]
    parts = rest.split('/')
    if not parts or not parts[0]:
        return f"URI pattern {applies_to!r}: missing host/bucket"
    host = parts[0]
    if not _LITERAL_SEG_RE.match(host):
        return f"URI pattern {applies_to!r}: host/bucket {host!r} contains disallowed characters"
    for seg in parts[1:]:
        err = _validate_uri_segment(seg)
        if err is not None:
            return f"URI pattern {applies_to!r}: {err}"
    return None


# ---------------------------------------------------------------------------
# YAML loading helpers
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a YAML mapping")
    return data


def _load_schema_at(rel_path: str) -> dict[str, Any]:
    schema_path = ROOT / rel_path
    with schema_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_schema(
    validator: Draft202012Validator, path: Path, record: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    for error in sorted(validator.iter_errors(record), key=lambda err: list(err.path)):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"{path.name}: schema: {location}: {error.message}")
    return errors


# ---------------------------------------------------------------------------
# Common checks (shared across versions)
# ---------------------------------------------------------------------------

def check_disallowed_fields(
    name: str, value: Any, location: str, errors: list[str]
) -> None:
    """Recursively reject private/disallowed field names."""
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_location = f"{location}.{key}" if location else key
            if key in DISALLOWED_FIELD_NAMES:
                errors.append(f"{name}: {nested_location}: field not permitted in public registry")
            if key == "generated_by_model":
                continue
            check_disallowed_fields(name, nested, nested_location, errors)
    elif isinstance(value, list):
        for i, nested in enumerate(value):
            check_disallowed_fields(name, nested, f"{location}[{i}]", errors)


def check_notes_string_shape(
    name: str, record: dict[str, Any], errors: list[str]
) -> None:
    """`notes` fields must be plain strings, never the copy object shape."""
    def _check(container: Any, path: str) -> None:
        if isinstance(container, dict) and container.get("notes") is not None:
            notes = container["notes"]
            if not isinstance(notes, str):
                errors.append(
                    f"{name}: {path}.notes must be a plain string, not a "
                    f"{type(notes).__name__}"
                )

    _check(record.get("sample_policy"), "sample_policy")
    _check(record.get("terms"), "terms")
    source = record.get("source") or {}
    for loc in source.get("locations") or []:
        if isinstance(loc, dict):
            loc_id = str(loc.get("id", ""))
            _check(loc.get("sample_policy"), f"source.locations[{loc_id!r}].sample_policy")
            _check(loc.get("terms"), f"source.locations[{loc_id!r}].terms")


def collect_ref_ids(refs: list[dict[str, Any]]) -> dict[str, str]:
    """Return {ref_id: ref_kind}."""
    result: dict[str, str] = {}
    if not isinstance(refs, list):
        return result
    for ref in refs:
        if isinstance(ref, dict):
            rid = str(ref.get("id", ""))
            rkind = str(ref.get("kind", ""))
            if rid:
                result[rid] = rkind
    return result


# ---------------------------------------------------------------------------
# Copy block warnings
# ---------------------------------------------------------------------------

_COPY_FIELDS = {"label", "headline", "lede", "text"}
_COPY_CHAINS: dict[str, list[str]] = {
    "label":    ["label", "headline", "text"],
    "headline": ["headline", "lede", "text"],
    "lede":     ["lede", "text", "headline"],
    "text":     ["text", "lede"],
}
_COPY_SLOTS = ["label", "headline", "lede", "text"]


def _cval(block: dict[str, Any], slot: str) -> str:
    for s in _COPY_CHAINS[slot]:
        v = block.get(s)
        if v not in (None, ""):
            return str(v)
    return ""


def _check_copy_block_warnings(
    name: str, block: Any, location: str, warnings: list[str],
) -> None:
    if not isinstance(block, dict):
        return
    if not _COPY_FIELDS.intersection(block.keys()):
        return
    ground = {sl: _cval(block, sl) for sl in _COPY_SLOTS}
    for field in ["lede", "headline", "label"]:
        if field not in block:
            continue
        trial = {k: v for k, v in block.items() if k != field}
        if all(_cval(trial, sl) == ground[sl] for sl in _COPY_SLOTS):
            warnings.append(
                f"{name}: {location}.{field}: redundant copy field — drop it"
            )


def _check_all_copy_block_warnings(
    name: str, obj: Any, location: str, warnings: list[str],
) -> None:
    if isinstance(obj, dict):
        if _COPY_FIELDS.intersection(obj.keys()):
            _check_copy_block_warnings(name, obj, location, warnings)
        else:
            for key, val in obj.items():
                _check_all_copy_block_warnings(
                    name, val, f"{location}.{key}" if location else key, warnings
                )
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _check_all_copy_block_warnings(name, item, f"{location}[{i}]", warnings)


# ---------------------------------------------------------------------------
# Effective-stewardship check
# ---------------------------------------------------------------------------

def _has_stewardship(obj: Any) -> bool:
    return (
        isinstance(obj, dict)
        and isinstance(obj.get("stewardship"), dict)
        and bool(obj["stewardship"])
    )


def check_effective_stewardship_v04(
    name: str, record: dict[str, Any], warnings: list[str],
    collection_has_stewardship: bool = False,
) -> None:
    """Warn if any annotation has no effective stewardship in a v0.4 record.

    `collection_has_stewardship` carries the collection.yaml record-level default
    into bucket-file validation: the collection default governs the whole
    collection (all bucket files), so a bucket-file annotation is covered when
    EITHER its own bucket file OR the collection.yaml carries a stewardship block.
    """
    record_stewardship = record.get("stewardship")
    has_record_default = (
        (isinstance(record_stewardship, dict) and bool(record_stewardship))
        or collection_has_stewardship
    )

    def _check_item(item: Any, location: str) -> None:
        if not isinstance(item, dict):
            return
        if not _has_stewardship(item) and not has_record_default:
            warnings.append(
                f"{name}: {location}: annotation has no stewardship block and "
                f"the record has no top-level stewardship default"
            )

    # summary / source_description
    for key in ("summary", "source_description"):
        val = record.get(key)
        if isinstance(val, dict):
            _check_item(val, key)

    # top-level facts[]
    for i, fact in enumerate(record.get("facts") or []):
        if isinstance(fact, dict):
            fact_id = str(fact.get("id", i))
            _check_item(fact, f"facts[{fact_id!r}]")

    # prefixes[].facts[] (bucket file only)
    for pi, pfx in enumerate(record.get("prefixes") or []):
        if not isinstance(pfx, dict):
            continue
        pfx_str = str(pfx.get("prefix", pi))
        for fi, fact in enumerate(pfx.get("facts") or []):
            if isinstance(fact, dict):
                fact_id = str(fact.get("id", fi))
                _check_item(fact, f"prefixes[{pfx_str!r}].facts[{fact_id!r}]")

    # source.locations[].facts[] (collection file only)
    for loc in (record.get("source") or {}).get("locations") or []:
        if not isinstance(loc, dict):
            continue
        loc_id = str(loc.get("id", ""))
        for fi, fact in enumerate(loc.get("facts") or []):
            if isinstance(fact, dict):
                fact_id = str(fact.get("id", fi))
                _check_item(fact, f"source.locations[{loc_id!r}].facts[{fact_id!r}]")

    # mirrors[].facts[] (bucket file only)
    for mirror in record.get("mirrors") or []:
        if not isinstance(mirror, dict):
            continue
        mirror_id = str(mirror.get("id", ""))
        for fi, fact in enumerate(mirror.get("facts") or []):
            if isinstance(fact, dict):
                fact_id = str(fact.get("id", fi))
                _check_item(fact, f"mirrors[{mirror_id!r}].facts[{fact_id!r}]")


# ---------------------------------------------------------------------------
# v0.4 fact validation
# ---------------------------------------------------------------------------

def validate_facts_v04(
    name: str,
    facts: list[Any],
    location: str,
    ref_ids: set[str],
    errors: list[str],
    warnings: list[str],
    seen_fact_ids: set[str],
) -> None:
    """Validate a facts[] list at any nesting position."""
    for i, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        fact_id = fact.get("id")
        ctx = f"{name}: {location}[{fact_id!r}]" if fact_id else f"{name}: {location}[{i}]"

        # id uniqueness (across all facts in file)
        if fact_id:
            fact_id_str = str(fact_id)
            if fact_id_str in seen_fact_ids:
                errors.append(f"{ctx}: duplicate fact id {fact_id_str!r} — ids must be unique across all facts in the file")
            seen_fact_ids.add(fact_id_str)

        # No applies_to or level fields (v0.3 fields must not appear)
        for dead_field in ("applies_to", "level", "display_scope"):
            if dead_field in fact:
                errors.append(f"{ctx}: field {dead_field!r} is not valid in v0.4 facts (subject is determined by nesting position)")

        # refs resolution
        for ref_id in fact.get("refs") or []:
            if ref_id not in ref_ids:
                errors.append(f"{ctx}.refs: {ref_id!r} not found in refs[]")

        # also: grammar
        for also_val in fact.get("also") or []:
            err = validate_relative_prefix(str(also_val), f"{ctx}.also")
            if err:
                errors.append(err)

        # relationship.target: must be an absolute URI (R7)
        rel = fact.get("relationship")
        if isinstance(rel, dict) and rel.get("target"):
            target = str(rel["target"])
            if "://" not in target:
                errors.append(f"{ctx}.relationship.target: {target!r} must be an absolute URI (e.g. s3://bucket/path/ or https://...)")

        # correction-prose heuristic in copy
        copy = fact.get("copy") or {}
        for tier in ("label", "headline", "lede", "text"):
            tier_val = copy.get(tier)
            if isinstance(tier_val, str) and _CORRECTION_DATE_RE.search(tier_val):
                warnings.append(
                    f"{ctx}.copy.{tier}: contains dated correction prose — "
                    f"audit trail prose belongs in the non-rendered 'note' field"
                )
                break


# ---------------------------------------------------------------------------
# v0.4 prefix validation
# ---------------------------------------------------------------------------

def validate_prefixes_v04(
    name: str,
    prefixes: list[Any],
    ref_ids: set[str],
    errors: list[str],
    warnings: list[str],
    seen_fact_ids: set[str],
    ref_ids_kinds: dict[str, str] | None = None,
) -> None:
    seen_prefix_values: set[str] = set()

    for i, pfx in enumerate(prefixes):
        if not isinstance(pfx, dict):
            continue
        prefix_val = pfx.get("prefix")
        ctx = f"{name}: prefixes[{prefix_val!r}]" if prefix_val else f"{name}: prefixes[{i}]"

        if not prefix_val:
            errors.append(f"{ctx}: prefix field is required")
            continue

        prefix_val = str(prefix_val)

        # Prefix grammar
        err = validate_relative_prefix(prefix_val, ctx)
        if err:
            errors.append(err)

        # Uniqueness
        if prefix_val in seen_prefix_values:
            errors.append(f"{ctx}: duplicate prefix {prefix_val!r} — prefix values must be unique within the file")
        seen_prefix_values.add(prefix_val)

        # refs resolution
        for ref_id in pfx.get("refs") or []:
            if ref_id not in ref_ids:
                errors.append(f"{ctx}.refs: {ref_id!r} not found in refs[]")

        # boundary must cite refs
        if pfx.get("boundary") is not None:
            pfx_refs = pfx.get("refs") or []
            if not pfx_refs:
                errors.append(f"{ctx}: boundary correction must cite at least one ref")
            elif ref_ids_kinds is not None:
                valid_kind_found = any(
                    ref_ids_kinds.get(r) in BOUNDARY_VALID_REF_KINDS
                    for r in pfx_refs
                )
                if not valid_kind_found:
                    errors.append(
                        f"{ctx}: boundary correction must cite at least one ref of kind "
                        f"{sorted(BOUNDARY_VALID_REF_KINDS)!r}"
                    )

        # defaults
        if pfx.get("coverage") == "full":
            warnings.append(f"{ctx}.coverage: value 'full' is the default — omit it")
        if pfx.get("confidence") == "high":
            warnings.append(f"{ctx}.confidence: value 'high' is the default — omit it")

        # bare table stub check
        kind_val = pfx.get("kind")
        copy_val = pfx.get("copy") or {}
        if isinstance(copy_val, dict):
            enrichment_fields = {
                "refs", "boundary", "featured", "terms", "declared_by", "expected_count",
                "drift", "facts", "confidence", "coverage", "note", "tags",
                "inherit", "stewardship", "id", "extent",
            }
            has_enrichment = any(pfx.get(f) for f in enrichment_fields)
            copy_keys = set(copy_val.keys())
            if (
                (kind_val is None or kind_val == "table")
                and copy_keys == {"label"}
                and not has_enrichment
            ):
                last_seg = prefix_val.rstrip("/").split("/")[-1]
                if copy_val.get("label") == last_seg:
                    warnings.append(
                        f"{ctx}: bare table stub — this prefix item carries no enrichment "
                        f"beyond a label equal to the path segment; omit it (see registry-model.md § Stub-elimination rule)"
                    )

        # id uniqueness tracked via seen_fact_ids (prefix ids use a different namespace)
        pfx_id = pfx.get("id")
        if pfx_id:
            pfx_id_str = f"prefix:{pfx_id}"
            if pfx_id_str in seen_fact_ids:
                errors.append(f"{ctx}.id: duplicate prefix id {pfx_id!r}")
            seen_fact_ids.add(pfx_id_str)

        # Nested facts
        facts = pfx.get("facts") or []
        if facts:
            validate_facts_v04(
                name, facts, f"prefixes[{prefix_val!r}].facts",
                ref_ids, errors, warnings, seen_fact_ids,
            )

        # expected_count source_ref resolution
        ec = pfx.get("expected_count")
        if isinstance(ec, dict):
            src_ref = ec.get("source_ref")
            if src_ref and src_ref not in ref_ids:
                errors.append(f"{ctx}.expected_count.source_ref: {src_ref!r} not found in refs[]")

        # correction-prose heuristic in copy
        copy = pfx.get("copy") or {}
        if isinstance(copy, dict):
            for tier in ("label", "headline", "lede", "text"):
                tier_val = copy.get(tier)
                if isinstance(tier_val, str) and _CORRECTION_DATE_RE.search(tier_val):
                    warnings.append(
                        f"{ctx}.copy.{tier}: contains dated correction prose — "
                        f"audit trail prose belongs in the non-rendered 'note' field"
                    )
                    break


def _ref_kind_for(ref_id: str, ref_ids_kinds: dict[str, str]) -> str:
    return ref_ids_kinds.get(ref_id, "")


# ---------------------------------------------------------------------------
# v0.4 collection-file validation
# ---------------------------------------------------------------------------

def validate_v04_collection_file(
    path: Path,
    record: dict[str, Any],
    seen_slugs: set[str],
    warnings: list[str],
) -> tuple[list[str], dict[str, str], set[str]]:
    """
    Validate a v0.4 collection.yaml file.
    Returns (errors, ref_ids_kinds, location_id_namespace).
    """
    errors: list[str] = []
    name = path.name

    # Copy-block hygiene warnings
    _check_all_copy_block_warnings(name, record, "", warnings)

    # Effective-stewardship check
    check_effective_stewardship_v04(name, record, warnings)

    # Disallowed fields
    check_disallowed_fields(name, record, "", errors)

    # notes shape
    check_notes_string_shape(name, record, errors)

    # Slug checks
    slug = str(record.get("slug", ""))
    if slug in RESERVED_SLUGS:
        errors.append(f"{name}: slug {slug!r} is reserved")
    if slug in seen_slugs:
        errors.append(f"{name}: duplicate slug {slug!r}")
    seen_slugs.add(slug)

    # terms display_policy gate
    terms = record.get("terms") or {}
    record_status = str(record.get("status", ""))
    if (
        isinstance(terms, dict)
        and terms.get("display_policy") == "include"
        and terms.get("status") != "verified"
    ):
        msg = (
            f"{name}: terms.display_policy 'include' requires "
            f"terms.status 'verified'"
        )
        if record_status in ("reviewed", "published"):
            errors.append(msg)
        else:
            warnings.append(f"{msg} (soft: record status is {record_status!r})")

    # Gather ref ids and kinds from top-level refs[]
    refs_list = record.get("refs") or []
    ref_ids_kinds: dict[str, str] = collect_ref_ids(refs_list)
    ref_ids: set[str] = set(ref_ids_kinds.keys())

    # Reject varve_inference refs
    for ref in refs_list:
        if not isinstance(ref, dict):
            continue
        if ref.get("kind") == "varve_inference":
            errors.append(
                f"{name}: refs[{ref.get('id')!r}]: kind 'varve_inference' "
                f"is not permitted in public records"
            )

    # Duplicate ref ids within this file
    seen_ref_ids: set[str] = set()
    for ref in refs_list:
        if not isinstance(ref, dict):
            continue
        rid = str(ref.get("id", ""))
        if rid in seen_ref_ids:
            errors.append(f"{name}: refs: duplicate ref id {rid!r}")
        seen_ref_ids.add(rid)

    # Build location-id namespace: source.locations[].id values
    # For the directory layout (D1): covers/superseded_by resolve into
    # {bucket file stems} ∪ {collection.yaml source.locations[].id}
    # The bucket-stem part is checked in validate_collection_dir.
    source = record.get("source") or {}
    non_bucket_locations = source.get("locations") or []
    location_id_namespace: set[str] = set()
    for loc in non_bucket_locations:
        if isinstance(loc, dict) and "id" in loc:
            location_id_namespace.add(str(loc["id"]))

    # Non-bucket backend required fields
    _NONBUCKET_BACKEND_REQUIRED: dict[str, list[str]] = {
        "http": ["base_url"],
        "ftp": ["base_url"],
        "huggingface": ["repo"],
        "zenodo": ["record_id"],
    }
    for loc in non_bucket_locations:
        if not isinstance(loc, dict):
            continue
        backend = str(loc.get("backend", ""))
        loc_id = str(loc.get("id", ""))
        for field in _NONBUCKET_BACKEND_REQUIRED.get(backend, []):
            if field not in loc:
                errors.append(
                    f"{name}: source.locations[{loc_id!r}]: backend {backend!r} "
                    f"requires field {field!r}"
                )

    # registry_entries ref resolution
    registry_entries = source.get("registry_entries") or []
    for entry in registry_entries:
        if not isinstance(entry, dict):
            continue
        registry = str(entry.get("registry", ""))
        ref_id = str(entry.get("ref", ""))
        if ref_id not in ref_ids:
            errors.append(
                f"{name}: source.registry_entries[{registry!r}]: ref {ref_id!r} "
                f"not found in refs[]"
            )
        elif registry == "aws_open_data":
            ref_url = ""
            for ref in refs_list:
                if isinstance(ref, dict) and str(ref.get("id", "")) == ref_id:
                    ref_url = str(ref.get("url", ""))
                    break
            if ref_url and AWS_ODR_GITHUB_PREFIX not in ref_url:
                warnings.append(
                    f"{name}: source.registry_entries[aws_open_data]: ref {ref_id!r} "
                    f"URL {ref_url!r} is not the GitHub source YAML"
                )

    # summary / source_description refs
    for key in ("summary", "source_description"):
        val = record.get(key)
        if isinstance(val, dict):
            for ref_id in val.get("refs") or []:
                if ref_id not in ref_ids:
                    errors.append(
                        f"{name}: {key}.refs: {ref_id!r} not found in refs[]"
                    )

    # review_guidance preferred_sources ref resolution
    review_guidance = record.get("review_guidance") or {}
    if isinstance(review_guidance, dict):
        for ref_id in review_guidance.get("preferred_sources") or []:
            if ref_id not in ref_ids:
                errors.append(
                    f"{name}: review_guidance.preferred_sources: "
                    f"{ref_id!r} not found in refs[]"
                )

    # display.report_issue_prefill refs
    slug = str(record.get("slug", ""))
    display = record.get("display") or {}
    prefill = (display.get("report_issue_prefill") if isinstance(display, dict) else None) or {}
    if isinstance(prefill, dict):
        if prefill.get("collection") and prefill["collection"] != slug:
            errors.append(
                f"{name}: display.report_issue_prefill.collection must match slug {slug!r}"
            )
        for ref_id in prefill.get("refs") or []:
            if ref_id not in ref_ids:
                errors.append(
                    f"{name}: display.report_issue_prefill.refs: "
                    f"{ref_id!r} not found in refs[]"
                )

    # Shared fact-id tracking
    seen_fact_ids: set[str] = set()

    # Top-level facts[] (collection-scoped)
    top_facts = record.get("facts") or []
    if top_facts:
        validate_facts_v04(
            name, top_facts, "facts",
            ref_ids, errors, warnings, seen_fact_ids,
        )

    # source.locations[].facts[]
    for loc in non_bucket_locations:
        if not isinstance(loc, dict):
            continue
        loc_id = str(loc.get("id", ""))
        loc_facts = loc.get("facts") or []
        if loc_facts:
            validate_facts_v04(
                name, loc_facts, f"source.locations[{loc_id!r}].facts",
                ref_ids, errors, warnings, seen_fact_ids,
            )

    # No prefixes[] allowed in collection.yaml
    if record.get("prefixes"):
        errors.append(f"{name}: prefixes[] must not appear in collection.yaml — prefixes belong in bucket files")

    # No bucket fields allowed in collection.yaml
    for bfield in ("bucket", "bucket_id", "backend", "role", "region",
                   "requester_pays", "account_required", "frozen", "superseded_by"):
        if bfield in record:
            errors.append(f"{name}: field {bfield!r} is not valid in collection.yaml — it belongs in a bucket file")

    return errors, ref_ids_kinds, location_id_namespace


# ---------------------------------------------------------------------------
# v0.4 bucket-file validation
# ---------------------------------------------------------------------------

def validate_v04_bucket_file(
    path: Path,
    record: dict[str, Any],
    collection_ref_ids_kinds: dict[str, str],
    warnings: list[str],
    collection_has_stewardship: bool = False,
) -> tuple[list[str], dict[str, str], set[str]]:
    """
    Validate a v0.4 bucket file (<bucket>.yaml within a collection directory).
    Returns (errors, bucket_ref_ids_kinds, seen_fact_ids).
    """
    errors: list[str] = []
    name = path.name
    expected_bucket = path.stem

    # Copy-block hygiene warnings
    _check_all_copy_block_warnings(name, record, "", warnings)

    # Effective-stewardship check — the collection.yaml record-level default
    # governs bucket-file annotations too (collection-as-default model).
    check_effective_stewardship_v04(
        name, record, warnings, collection_has_stewardship=collection_has_stewardship
    )

    # Disallowed fields
    check_disallowed_fields(name, record, "", errors)

    # notes shape
    check_notes_string_shape(name, record, errors)

    # The filename stem is the Outcrop bucket identity: outcrop_bucket (the db-slug we
    # ingested under) for a renamed/prefix product, else bucket (the real S3 name). (D1)
    bucket = str(record.get("bucket", ""))
    identity = str(record.get("outcrop_bucket") or bucket)
    if identity != expected_bucket:
        errors.append(
            f"{name}: bucket identity (outcrop_bucket or bucket) {identity!r} "
            f"must equal the filename stem {expected_bucket!r}"
        )

    # Bucket-local refs (supplement collection refs)
    bucket_refs_list = record.get("refs") or []
    bucket_ref_ids_kinds: dict[str, str] = collect_ref_ids(bucket_refs_list)

    # Reject varve_inference refs
    for ref in bucket_refs_list:
        if not isinstance(ref, dict):
            continue
        if ref.get("kind") == "varve_inference":
            errors.append(
                f"{name}: refs[{ref.get('id')!r}]: kind 'varve_inference' "
                f"is not permitted in public records"
            )

    # Duplicate ref ids within this file
    seen_ref_ids: set[str] = set()
    for ref in bucket_refs_list:
        if not isinstance(ref, dict):
            continue
        rid = str(ref.get("id", ""))
        if rid in seen_ref_ids:
            errors.append(f"{name}: refs: duplicate ref id {rid!r}")
        seen_ref_ids.add(rid)

    # Combined ref pool for resolution (local-file-first, then collection)
    combined_ref_ids_kinds = {**collection_ref_ids_kinds, **bucket_ref_ids_kinds}
    combined_ref_ids: set[str] = set(combined_ref_ids_kinds.keys())

    # terms display_policy gate (bucket file may override)
    terms = record.get("terms") or {}
    if (
        isinstance(terms, dict)
        and terms.get("display_policy") == "include"
        and terms.get("status") != "verified"
    ):
        msg = (
            f"{name}: terms.display_policy 'include' requires "
            f"terms.status 'verified'"
        )
        warnings.append(f"{msg} (soft: bucket file)")

    # Shared fact-id tracking
    seen_fact_ids: set[str] = set()

    # Top-level facts[] (bucket-scoped)
    top_facts = record.get("facts") or []
    if top_facts:
        validate_facts_v04(
            name, top_facts, "facts",
            combined_ref_ids, errors, warnings, seen_fact_ids,
        )

    # Soft cap: total facts
    all_fact_count = len(top_facts)
    for pfx in record.get("prefixes") or []:
        if isinstance(pfx, dict):
            all_fact_count += len(pfx.get("facts") or [])
    if all_fact_count > 30:
        warnings.append(
            f"{name}: total facts across all nesting positions is {all_fact_count} — "
            f"soft cap is 30 (review whether all are needed)"
        )

    # prefixes[]
    prefixes = record.get("prefixes") or []
    if len(prefixes) > 150:
        warnings.append(
            f"{name}: prefixes[] has {len(prefixes)} items — consider using pattern prefixes "
            f"or expected_count catalog pointers; enumerate collection-shaping prefixes only "
            f"(soft cap: 150)"
        )

    validate_prefixes_v04(
        name, prefixes, combined_ref_ids, errors, warnings, seen_fact_ids,
        ref_ids_kinds=combined_ref_ids_kinds,
    )

    # mirrors[]
    mirrors = record.get("mirrors") or []
    seen_mirror_ids: set[str] = set()
    _MIRROR_BACKEND_REQUIRED: dict[str, list[str]] = {
        "http": ["base_url"],
        "ftp": ["base_url"],
        "huggingface": ["repo"],
        "zenodo": ["record_id"],
    }
    for mi, mirror in enumerate(mirrors):
        if not isinstance(mirror, dict):
            continue
        mirror_id = str(mirror.get("id", ""))
        ctx = f"{name}: mirrors[{mirror_id!r}]" if mirror_id else f"{name}: mirrors[{mi}]"

        # Required fields: id, backend, role
        for req in ("id", "backend", "role"):
            if not mirror.get(req):
                errors.append(f"{ctx}: required field {req!r} is missing or empty")

        # Duplicate mirror ids within this file
        if mirror_id:
            if mirror_id in seen_mirror_ids:
                errors.append(f"{ctx}: duplicate mirror id {mirror_id!r}")
            seen_mirror_ids.add(mirror_id)

        # backend-specific required fields
        backend = str(mirror.get("backend", ""))
        for field in _MIRROR_BACKEND_REQUIRED.get(backend, []):
            if not mirror.get(field):
                errors.append(f"{ctx}: backend {backend!r} requires field {field!r}")

        # superseded_by on a mirror: resolved within the same file's mirror ids
        # (cross-sibling references are resolved after all mirror ids are collected)
        mirror_superseded_by = mirror.get("superseded_by")
        if mirror_superseded_by and str(mirror_superseded_by) not in seen_mirror_ids:
            # Defer check: collect all ids first then re-check below
            pass

        # mirror facts[]
        mirror_facts = mirror.get("facts") or []
        if mirror_facts:
            validate_facts_v04(
                name, mirror_facts, f"mirrors[{mirror_id!r}].facts",
                combined_ref_ids, errors, warnings, seen_fact_ids,
            )

    # Deferred: validate mirror superseded_by against all mirror ids in this file
    all_mirror_ids = {str(m.get("id", "")) for m in mirrors if isinstance(m, dict) and m.get("id")}
    for mi, mirror in enumerate(mirrors):
        if not isinstance(mirror, dict):
            continue
        mirror_id = str(mirror.get("id", ""))
        ctx = f"{name}: mirrors[{mirror_id!r}]" if mirror_id else f"{name}: mirrors[{mi}]"
        mirror_superseded_by = mirror.get("superseded_by")
        if mirror_superseded_by and str(mirror_superseded_by) not in all_mirror_ids:
            errors.append(
                f"{ctx}: superseded_by {mirror_superseded_by!r} does not resolve into "
                f"any mirror id in this file (known: {sorted(all_mirror_ids)!r})"
            )

    return errors, bucket_ref_ids_kinds, seen_fact_ids


# ---------------------------------------------------------------------------
# Cross-file (whole-directory) validation
# ---------------------------------------------------------------------------

def validate_collection_dir(
    coll_dir: Path,
    collection_record: dict[str, Any],
    bucket_records: list[tuple[Path, dict[str, Any]]],
    seen_slugs: set[str],
    warnings: list[str],
) -> list[str]:
    """
    Cross-file rules for a v0.4 collection directory.
    Called after per-file validators have run.
    """
    errors: list[str] = []
    slug = str(collection_record.get("slug", ""))
    coll_name = "collection.yaml"

    # Compute id namespace: bucket file stems ∪ bucket-file mirrors[].id ∪ collection.yaml source.locations[].id
    bucket_stems: set[str] = {p.stem for p, _ in bucket_records}
    source = collection_record.get("source") or {}
    location_ids: set[str] = {
        str(loc.get("id", ""))
        for loc in (source.get("locations") or [])
        if isinstance(loc, dict) and loc.get("id")
    }
    # Mirror ids from all bucket files
    mirror_ids: set[str] = set()
    for _, brec in bucket_records:
        for m in brec.get("mirrors") or []:
            if isinstance(m, dict) and m.get("id"):
                mirror_ids.add(str(m["id"]))
    full_id_namespace = bucket_stems | location_ids | mirror_ids

    # superseded_by in each bucket file must resolve into the full namespace
    for bpath, brec in bucket_records:
        superseded_by = brec.get("superseded_by")
        if superseded_by and str(superseded_by) not in full_id_namespace:
            errors.append(
                f"{bpath.name}: superseded_by {superseded_by!r} does not resolve into "
                f"the collection id namespace (bucket stems: {sorted(bucket_stems)!r}, "
                f"mirror ids: {sorted(mirror_ids)!r}, "
                f"location ids: {sorted(location_ids)!r})"
            )

    # sponsorships.covers must resolve into full_id_namespace
    sponsorships = source.get("sponsorships") or []
    for sp in sponsorships:
        if not isinstance(sp, dict):
            continue
        for covered_id in sp.get("covers") or []:
            if covered_id not in full_id_namespace:
                errors.append(
                    f"{coll_name}: source.sponsorships[{sp.get('program')!r}].covers: "
                    f"{covered_id!r} is not a bucket name or location id "
                    f"(known: {sorted(full_id_namespace)!r})"
                )

    # Ref-id uniqueness across the whole collection directory (R2)
    # A ref id appearing in both collection.yaml and any bucket file is an error.
    collection_ref_ids = set(collect_ref_ids(collection_record.get("refs") or []).keys())
    for bpath, brec in bucket_records:
        bucket_ref_ids = set(collect_ref_ids(brec.get("refs") or []).keys())
        dup_refs = collection_ref_ids & bucket_ref_ids
        for dup in sorted(dup_refs):
            errors.append(
                f"{bpath.name}: refs: ref id {dup!r} is already declared in "
                f"collection.yaml refs — each ref id must appear in exactly one file"
            )

    # Build combined ref pool for orphan-ref check (R6)
    combined_ref_ids: set[str] = set(collection_ref_ids)
    for _, brec in bucket_records:
        combined_ref_ids |= set(collect_ref_ids(brec.get("refs") or []).keys())

    # Posture only-tightens (cross-file check)
    coll_sensitivity = str(collection_record.get("sensitivity_class", ""))
    coll_publication = str(collection_record.get("publication_scope", ""))
    for bpath, brec in bucket_records:
        b_sensitivity = str(brec.get("sensitivity_class", ""))
        b_publication = str(brec.get("publication_scope", ""))
        if b_sensitivity and coll_sensitivity:
            cs = SENSITIVITY_ORDER.get(coll_sensitivity, 0)
            bs = SENSITIVITY_ORDER.get(b_sensitivity, 0)
            if bs < cs:
                errors.append(
                    f"{bpath.name}: sensitivity_class {b_sensitivity!r} is less restrictive "
                    f"than collection default {coll_sensitivity!r} — bucket posture may only tighten"
                )
        if b_publication and coll_publication:
            cp = PUBLICATION_ORDER.get(coll_publication, 0)
            bp = PUBLICATION_ORDER.get(b_publication, 0)
            if bp < cp:
                errors.append(
                    f"{bpath.name}: publication_scope {b_publication!r} is less restrictive "
                    f"than collection default {coll_publication!r} — bucket posture may only tighten"
                )

    # Fact-id uniqueness across the whole collection (R2)
    seen_fact_ids_global: set[str] = set()

    def _collect_fact_ids(record: dict[str, Any], file_name: str) -> None:
        for fact in record.get("facts") or []:
            if isinstance(fact, dict) and fact.get("id"):
                fid = str(fact["id"])
                if fid in seen_fact_ids_global:
                    errors.append(
                        f"{file_name}: fact id {fid!r} is already declared in another file "
                        f"in this collection — fact ids must be unique across the collection"
                    )
                seen_fact_ids_global.add(fid)
        for pfx in record.get("prefixes") or []:
            if not isinstance(pfx, dict):
                continue
            for fact in pfx.get("facts") or []:
                if isinstance(fact, dict) and fact.get("id"):
                    fid = str(fact["id"])
                    if fid in seen_fact_ids_global:
                        errors.append(
                            f"{file_name}: fact id {fid!r} is already declared in another file "
                            f"in this collection — fact ids must be unique across the collection"
                        )
                    seen_fact_ids_global.add(fid)
        for loc in (record.get("source") or {}).get("locations") or []:
            if not isinstance(loc, dict):
                continue
            for fact in loc.get("facts") or []:
                if isinstance(fact, dict) and fact.get("id"):
                    fid = str(fact["id"])
                    if fid in seen_fact_ids_global:
                        errors.append(
                            f"{file_name}: fact id {fid!r} is already declared in another file "
                            f"in this collection — fact ids must be unique across the collection"
                        )
                    seen_fact_ids_global.add(fid)
        for mirror in record.get("mirrors") or []:
            if not isinstance(mirror, dict):
                continue
            for fact in mirror.get("facts") or []:
                if isinstance(fact, dict) and fact.get("id"):
                    fid = str(fact["id"])
                    if fid in seen_fact_ids_global:
                        errors.append(
                            f"{file_name}: fact id {fid!r} is already declared in another file "
                            f"in this collection — fact ids must be unique across the collection"
                        )
                    seen_fact_ids_global.add(fid)

    _collect_fact_ids(collection_record, coll_name)
    for bpath, brec in bucket_records:
        _collect_fact_ids(brec, bpath.name)

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # Schema routing:
    #   "0.4" collection.yaml → schema/collection.schema.json
    #   "0.4" bucket file → schema/bucket.schema.json
    schemas: dict[str, dict[str, Any]] = {
        "0.4_collection": _load_schema_at("schema/collection.schema.json"),
        "0.4_bucket": _load_schema_at("schema/bucket.schema.json"),
    }
    validators: dict[str, Draft202012Validator] = {}
    for ver, schema_doc in schemas.items():
        Draft202012Validator.check_schema(schema_doc)
        validators[ver] = Draft202012Validator(
            schema_doc, format_checker=Draft202012Validator.FORMAT_CHECKER
        )

    errors: list[str] = []
    warnings: list[str] = []
    seen_slugs: set[str] = set()

    collections_dir = ROOT / "collections"

    # Glob collection directories
    coll_dirs = sorted(
        d for d in collections_dir.iterdir()
        if d.is_dir() and d.name != "__pycache__"
    )

    for coll_dir in coll_dirs:
        coll_yaml = coll_dir / "collection.yaml"
        if not coll_yaml.exists():
            errors.append(f"{coll_dir.name}/: missing collection.yaml")
            continue

        # Load and validate collection.yaml
        try:
            coll_record = load_yaml(coll_yaml)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{coll_dir.name}/collection.yaml: {exc}")
            continue

        sv = str(coll_record.get("schema_version", ""))
        if sv != "0.4":
            errors.append(f"{coll_dir.name}/collection.yaml: schema_version must be '0.4', got {sv!r}")
            continue

        errors.extend(validate_schema(validators["0.4_collection"], coll_yaml, coll_record))
        coll_errors, coll_ref_ids_kinds, coll_location_ids = validate_v04_collection_file(
            coll_yaml, coll_record, seen_slugs, warnings
        )
        errors.extend(coll_errors)

        # Find bucket files (all *.yaml in dir except collection.yaml)
        bucket_paths = sorted(
            p for p in coll_dir.glob("*.yaml")
            if p.name != "collection.yaml"
        )

        if not bucket_paths:
            errors.append(f"{coll_dir.name}/: no bucket files found (need at least one <bucket>.yaml)")
            continue

        bucket_records: list[tuple[Path, dict[str, Any]]] = []

        for bpath in bucket_paths:
            try:
                brec = load_yaml(bpath)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{coll_dir.name}/{bpath.name}: {exc}")
                continue

            bsv = str(brec.get("schema_version", ""))
            if bsv != "0.4":
                errors.append(f"{coll_dir.name}/{bpath.name}: schema_version must be '0.4', got {bsv!r}")
                continue

            errors.extend(validate_schema(validators["0.4_bucket"], bpath, brec))
            coll_stewardship = coll_record.get("stewardship")
            coll_has_stewardship = isinstance(coll_stewardship, dict) and bool(coll_stewardship)
            b_errors, _, _ = validate_v04_bucket_file(
                bpath, brec, coll_ref_ids_kinds, warnings,
                collection_has_stewardship=coll_has_stewardship,
            )
            errors.extend(b_errors)
            bucket_records.append((bpath, brec))

        # Cross-file rules
        if bucket_records:
            dir_errors = validate_collection_dir(
                coll_dir, coll_record, bucket_records, seen_slugs, warnings
            )
            errors.extend(dir_errors)

    if warnings:
        print("Warnings:", file=sys.stderr)
        print("\n".join(f"  WARN  {w}" for w in warnings), file=sys.stderr)

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print("Registry validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
